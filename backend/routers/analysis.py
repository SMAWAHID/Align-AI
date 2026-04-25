"""
POST /api/v1/analyze — core analysis endpoint.

Pipeline:
  1. Validate file + size
  2. Extract PDF text in-memory
  3. Generate embeddings concurrently
  4. Compute hybrid score
  5. If score < threshold → gap analysis
  6. If gap analysis → find skill resources concurrently
  7. Build ATS resume
  8. Persist to PostgreSQL
  9. Return structured response
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models import MatchHistory
from ..schemas import AnalysisResponse, ScoreBreakdown
from ..services.ai_service import (
    analyse_gap,
    calculate_hybrid_score,
    find_skill_resources,
    get_embeddings,
)
from ..services.pdf_service import extract_text_from_bytes
from ..services.resume_builder import build_ats_resume

logger   = logging.getLogger(__name__)
settings = get_settings()
limiter  = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse, summary="Analyse resume against a job description")
@limiter.limit(settings.rate_limit_analyze)
async def analyze(
    request: Request,
    resume: UploadFile = File(...),
    job_description: str = Form(..., min_length=50, max_length=20_000),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:

    # 1. Validate
    if resume.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail={"code": "INVALID_CONTENT_TYPE", "message": "Only PDF files are accepted.", "field": "resume"})

    pdf_bytes = await resume.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty.", "field": "resume"})
    if len(pdf_bytes) > settings.max_file_size_bytes:
        raise HTTPException(status_code=400, detail={"code": "FILE_TOO_LARGE", "message": f"File exceeds {settings.max_file_size_mb} MB.", "field": "resume"})

    jd_text = job_description.strip()

    # 2. Extract PDF text
    logger.info("Extracting text from %s (%d bytes)", resume.filename, len(pdf_bytes))
    resume_text = extract_text_from_bytes(pdf_bytes, resume.filename or "resume.pdf")

    # 3. Embeddings
    logger.info("Generating embeddings for %s", resume.filename)
    embeddings = await get_embeddings(resume_text, jd_text)

    # 4. Score
    score = await calculate_hybrid_score(resume_text, jd_text, embeddings)
    logger.info("Scores — final=%.1f semantic=%.1f keyword=%.1f", score.final, score.semantic, score.keyword)

    # 5+6. Gap analysis + skill resources (concurrent)
    gap_report = None
    if score.final < settings.gap_analysis_threshold:
        logger.info("Score %.1f < %.1f — running gap analysis", score.final, settings.gap_analysis_threshold)
        gap_report = await analyse_gap(resume_text, jd_text, score.missing_tokens, score.final)

        # Fetch skill resources concurrently alongside ATS resume build
        import asyncio
        resources_task = asyncio.create_task(find_skill_resources(gap_report.missing_skills))

    # 7. ATS resume
    logger.info("Building ATS resume for %s", resume.filename)
    ats_resume_md = await build_ats_resume(resume_text, jd_text, resume.filename or "resume.pdf")

    # Collect skill resources if gap analysis ran
    if gap_report is not None:
        gap_report.skill_resources = await resources_task  # type: ignore[name-defined]

    # 8. Persist
    history_row = MatchHistory(
        filename=resume.filename or "resume.pdf",
        job_description_snippet=jd_text[:500],
        match_score=score.final,
        semantic_score=score.semantic,
        keyword_score=score.keyword,
        gap_analysis=gap_report.model_dump() if gap_report else None,
        ats_resume=ats_resume_md,
        created_at=datetime.now(timezone.utc),
    )
    db.add(history_row)
    await db.flush()
    await db.refresh(history_row)

    # 9. Response
    return AnalysisResponse(
        id=history_row.id,
        filename=history_row.filename,
        score_breakdown=ScoreBreakdown(semantic=score.semantic, keyword=score.keyword, final=score.final),
        gap_analysis=gap_report,
        ats_resume=ats_resume_md,
        created_at=history_row.created_at,
    )
