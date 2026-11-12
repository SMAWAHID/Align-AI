"""
Resume-specific endpoints:
  POST /api/v1/resume/enhance   — incorporate selected skills + improvements
  POST /api/v1/resume/download  — convert Markdown to txt/md/pdf/docx
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models import MatchHistory
from ..core.security import CurrentUser
from ..schemas import EnhanceResumeRequest, EnhanceResumeResponse
from ..services.ai_service import _PROVIDER
from ..services.resume_builder import convert_resume, enhance_resume

logger   = logging.getLogger(__name__)
settings = get_settings()
limiter  = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/resume", tags=["resume"])


# ─── Enhance ─────────────────────────────────────────────────────────────────

@router.post(
    "/enhance",
    response_model=EnhanceResumeResponse,
    summary="Enhance ATS resume with selected skills and improvements",
)
@limiter.limit("10/minute")
async def enhance(
    request: Request,
    user: CurrentUser,
    body: EnhanceResumeRequest,
    db: AsyncSession = Depends(get_db),
) -> EnhanceResumeResponse:
    enhanced_md = await enhance_resume(
        current_resume=body.current_resume,
        selected_skills=body.selected_skills,
        selected_improvements=body.selected_improvements,
        job_description=body.job_description,
    )
    return EnhanceResumeResponse(enhanced_resume=enhanced_md, provider=_PROVIDER)


# ─── Download ────────────────────────────────────────────────────────────────

class DownloadRequest(BaseModel):
    content: str = Field(..., min_length=50, description="Markdown resume content")
    format: Literal["txt", "md", "pdf", "docx"] = "pdf"
    filename: str = Field(default="resume", max_length=100)


@router.post(
    "/download",
    summary="Convert Markdown resume to txt / md / pdf / docx",
    responses={
        200: {"description": "File download"},
        400: {"description": "Invalid format"},
        500: {"description": "Conversion failed"},
    },
)
@limiter.limit("20/minute")
async def download(
    request: Request,
    user: CurrentUser,
    body: DownloadRequest,
) -> Response:
    try:
        file_bytes, media_type, ext = convert_resume(body.content, body.format)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FORMAT", "message": str(exc)})

    # Sanitise filename
    safe_name = "".join(c for c in body.filename if c.isalnum() or c in "-_ ").strip() or "resume"
    safe_name = safe_name.replace(" ", "_")

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}{ext}"'},
    )
