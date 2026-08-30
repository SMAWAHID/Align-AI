"""
GET /api/v1/history  — paginated analysis history
GET /api/v1/history/{id} — single record with full ats_resume
DELETE /api/v1/history/{id} — delete a record
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..core.security import CurrentUser
from ..database import get_db
from ..models import MatchHistory
from ..schemas import AnalysisResponse, HistoryItem, HistoryResponse, ScoreBreakdown

logger = logging.getLogger(__name__)
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("", response_model=HistoryResponse, summary="List past analyses (paginated)")
@limiter.limit(settings.rate_limit_history)
async def list_history(
    request: Request,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    offset = (page - 1) * page_size

    # Every query is filtered by owner — history is per-account, and the count
    # must use the same filter or pagination reports other people's rows.
    count_q = (
        select(func.count())
        .select_from(MatchHistory)
        .where(MatchHistory.user_id == user.id)
    )
    total: int = (await db.execute(count_q)).scalar_one()

    rows_q = (
        select(MatchHistory)
        .where(MatchHistory.user_id == user.id)
        .order_by(MatchHistory.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(rows_q)).scalars().all()

    items = [
        HistoryItem(
            id=r.id,
            filename=r.filename,
            job_description_snippet=r.job_description_snippet,
            match_score=r.match_score,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return HistoryResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{record_id}", response_model=AnalysisResponse, summary="Get a single analysis record")
@limiter.limit(settings.rate_limit_history)
async def get_history_item(
    request: Request,
    record_id: int,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    row = await _get_owned_or_404(record_id, user.id, db)
    from ..schemas import GapAnalysisReport

    gap = GapAnalysisReport.model_validate(row.gap_analysis) if row.gap_analysis else None
    return AnalysisResponse(
        id=row.id,
        filename=row.filename,
        score_breakdown=ScoreBreakdown(
            semantic=row.semantic_score,
            keyword=row.keyword_score,
            final=row.match_score,
        ),
        gap_analysis=gap,
        ats_resume=row.ats_resume,
        created_at=row.created_at,
    )


@router.delete("/{record_id}", status_code=204, summary="Delete an analysis record")
@limiter.limit(settings.rate_limit_history)
async def delete_history_item(
    request: Request,
    record_id: int,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await _get_owned_or_404(record_id, user.id, db)
    await db.delete(row)


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _get_owned_or_404(record_id: int, user_id: int, db: AsyncSession) -> MatchHistory:
    """Fetch a record, or 404 if it does not exist OR belongs to someone else.

    Returning 404 rather than 403 for a record owned by another account is
    deliberate: a 403 would confirm that the id exists, letting anyone map out
    how many analyses other users have run.
    """
    result = await db.get(MatchHistory, record_id)
    if result is None or result.user_id != user_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Record {record_id} not found."},
        )
    return result
