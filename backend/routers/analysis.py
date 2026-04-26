"""
POST /api/v1/analyze — core analysis endpoint.
Accepts PDF, DOCX, and TXT resumes.
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
from ..services.document_service import extract_text
from ..services.resume_builder import build_ats_resume

logger   = logging.getLogger(__name__)
settings = get_settings()
limiter  = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

_ACCEPTED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/octet-stream",   # browsers sometimes send this for .docx
}

_ACCEPTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@router.post("/analyze", response_model=AnalysisResponse, summary="Analyse resume against a job description")
@limiter.limit(settings.rate_limit_analyze)
async def analyze(
    request: Request,
    resume: UploadFile = File(...),
    job_description: str = Form(..., min_length=50, max_length=20_000),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:

    # ── 1. Validate file type ─────────────────────────────────────────────────
    filename  = resume.filename or "resume"
    name_lower = filename.lower()
    ext = next((e for e in _ACCEPTED_EXTENSIONS if name_lower.endswith(e)), None)

    if resume.content_type not in _ACCEPTED_TYPES and ext is None:
        raise HTTPException(
            status_code=415,
            detail={
                "code": "INVALID_CONTENT_TYPE",
                "message": "Only PDF, DOCX, and TXT files are accepted.",
                "field": "resume",
            },
        )

    file_bytes = await resume.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty.", "field": "resume"})
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(status_code=400, detail={"code": "FILE_TOO_LARGE", "message": f"File exceeds {settings.max_file_size_mb} MB.", "field": "resume"})

    jd_text = job_description.strip()

    # ── 2. Extract text ────────────────────────────────────────────────────────
    logger.info("Extracting text from %s (%d bytes)", filename, len(file_bytes))
    resume_text = extract_text(file_bytes, filename, resume.content_type or "")

    # ── 3. Embeddings ──────────────────────────────────────────────────────────
    logger.info("Generating embeddings for %s", filename)
    embeddings = await get_embeddings(resume_text, jd_text)

    # ── 4. Score ───────────────────────────────────────────────────────────────
    score = await calculate_hybrid_score(resume_text, jd_text, embeddings)
    logger.info("Scores — final=%.1f semantic=%.1f keyword=%.1f", score.final, score.semantic, score.keyword)

    # ── 5+6. Gap analysis + skill resources ────────────────────────────────────
    import asyncio
    gap_report    = None
    resources_task = None

    if score.final < settings.gap_analysis_threshold:
        logger.info("Score %.1f < %.1f — running gap analysis", score.final, settings.gap_analysis_threshold)
        gap_report     = await analyse_gap(resume_text, jd_text, score.missing_tokens, score.final)
        resources_task = asyncio.create_task(find_skill_resources(gap_report.missing_skills))

    # ── 7. ATS resume ──────────────────────────────────────────────────────────
    logger.info("Building ATS resume for %s", filename)
    ats_resume_md = await build_ats_resume(resume_text, jd_text, filename)

    if gap_report is not None and resources_task is not None:
        gap_report.skill_resources = await resources_task

    # ── 8. Persist ─────────────────────────────────────────────────────────────
    history_row = MatchHistory(
        filename=filename,
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

    return AnalysisResponse(
        id=history_row.id,
        filename=filename,
        score_breakdown=ScoreBreakdown(semantic=score.semantic, keyword=score.keyword, final=score.final),
        gap_analysis=gap_report,
        ats_resume=ats_resume_md,
        created_at=history_row.created_at,
    )
