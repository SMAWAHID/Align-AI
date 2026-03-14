"""
Pydantic v2 schemas — the shared contract between FastAPI backend
and the Next.js frontend (mirrored in types/api.ts).

Validation is strict: extra fields are forbidden so the frontend
never receives unexpected data that could cause runtime errors.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ─── Sub-models ──────────────────────────────────────────────────────────────

class GapAnalysisReport(BaseModel):
    """
    Structured output from Gemini Flash gap-analysis prompt.
    Frontend renders each list as an accordion section.
    """
    missing_skills: list[str] = Field(
        default_factory=list,
        description="Skills/tools present in JD but absent from resume",
        max_length=30,
    )
    improvements: list[str] = Field(
        default_factory=list,
        description="Concrete, actionable improvement suggestions",
        max_length=20,
    )
    match_summary: str = Field(
        default="",
        description="2-3 sentence overall assessment",
        max_length=1000,
    )

    @field_validator("missing_skills", "improvements", mode="before")
    @classmethod
    def clamp_list(cls, v: list) -> list:
        return v[:30] if isinstance(v, list) else []


class ScoreBreakdown(BaseModel):
    """Detailed scoring breakdown for the frontend chart."""
    semantic: float = Field(ge=0, le=100, description="Embedding cosine similarity (0–100)")
    keyword: float = Field(ge=0, le=100, description="Keyword/phrase overlap (0–100)")
    final: float = Field(ge=0, le=100, description="Weighted composite score")


# ─── Request / Response ──────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    """
    Full response from POST /api/v1/analyze.
    Mirrors frontend AnalysisResult type in types/api.ts.
    """
    model_config = {"from_attributes": True}

    id: int
    filename: str
    score_breakdown: ScoreBreakdown
    gap_analysis: Optional[GapAnalysisReport] = Field(
        None,
        description="Only present when final score < threshold (default 85%)",
    )
    ats_resume: Optional[str] = Field(
        None,
        description="ATS-optimised resume in Markdown format",
    )
    created_at: datetime


class HistoryItem(BaseModel):
    """Lightweight row for the history list."""
    model_config = {"from_attributes": True}

    id: int
    filename: str
    job_description_snippet: str
    match_score: float
    created_at: datetime


class HistoryResponse(BaseModel):
    """Paginated history response."""
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int


class ErrorDetail(BaseModel):
    """Structured error payload. Never leaks stack traces in production."""
    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable message")
    field: Optional[str] = Field(None, description="Offending field, if applicable")


class ErrorResponse(BaseModel):
    """Envelope for all 4xx / 5xx responses."""
    detail: ErrorDetail
