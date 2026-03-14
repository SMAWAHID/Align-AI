"""
SQLAlchemy 2.0 ORM models using mapped_column with full type annotations.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class MatchHistory(Base):
    """Stores each resume-JD analysis result."""
    __tablename__ = "match_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)

    # Source metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    job_description_snippet: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="First 500 chars of JD for display in history",
    )

    # Scores (0–100 range, stored as floats)
    match_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Weighted hybrid score (semantic 60% + keyword 40%)",
    )
    semantic_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Cosine similarity of Gemini embeddings × 100",
    )
    keyword_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Keyword/phrase overlap score × 100",
    )

    # AI-generated content (nullable — only set when score < threshold)
    gap_analysis: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured gap report from Gemini Flash",
    )

    # ATS-optimised resume text (Markdown)
    ats_resume: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI-rewritten ATS-friendly resume in Markdown",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<MatchHistory id={self.id} file={self.filename!r} "
            f"score={self.match_score:.1f}>"
        )
