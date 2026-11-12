"""
Pydantic v2 schemas — shared contract between FastAPI backend
and the Next.js frontend (mirrored in types/api.ts).
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Sub-models ──────────────────────────────────────────────────────────────

class SkillResource(BaseModel):
    """A single learning resource for a missing skill."""
    title: str
    url: str
    type: Literal["docs", "course", "video", "tutorial", "other"] = "other"


class SkillWithResources(BaseModel):
    """A missing skill paired with curated learning resources."""
    skill: str
    resources: list[SkillResource] = Field(default_factory=list, max_length=4)


class GapAnalysisReport(BaseModel):
    """Structured output from the gap analysis LLM call."""
    missing_skills: list[str] = Field(default_factory=list, max_length=30)
    skill_resources: list[SkillWithResources] = Field(
        default_factory=list,
        description="Curated learning resources per missing skill",
    )
    improvements: list[str] = Field(default_factory=list, max_length=20)
    match_summary: str = Field(default="", max_length=1000)

    @field_validator("missing_skills", "improvements", mode="before")
    @classmethod
    def clamp_list(cls, v: list) -> list:
        return v[:30] if isinstance(v, list) else []


class ScoreBreakdown(BaseModel):
    semantic: float = Field(ge=0, le=100)
    keyword: float = Field(ge=0, le=100)
    final: float = Field(ge=0, le=100)


# ─── Request / Response ──────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    filename: str
    score_breakdown: ScoreBreakdown
    gap_analysis: Optional[GapAnalysisReport] = None
    ats_resume: Optional[str] = None
    created_at: datetime


class HistoryItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    filename: str
    job_description_snippet: str
    match_score: float
    created_at: datetime


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int


# ─── Resume enhance / download ───────────────────────────────────────────────

class EnhanceResumeRequest(BaseModel):
    """Request body for POST /api/v1/resume/enhance"""
    current_resume: str = Field(
        ...,
        min_length=100,
        description="Current ATS resume in Markdown",
    )
    selected_skills: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="Missing skills the user wants incorporated",
    )
    selected_improvements: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Improvement suggestions the user wants applied",
    )
    job_description: str = Field(
        ...,
        min_length=50,
        max_length=20_000,
    )


class EnhanceResumeResponse(BaseModel):
    enhanced_resume: str
    provider: str


class DownloadFormat(str):
    pass


# ─── Errors ──────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail


# ─── Auth ────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    # bcrypt only reads the first 72 bytes, so cap the input rather than let two
    # different long passwords open the same account.
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut
