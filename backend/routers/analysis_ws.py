"""
WebSocket endpoint: ws://localhost:8000/api/v1/ws/analyze

Streams real server-side pipeline progress events to the frontend
as JSON messages, then sends the final result.

Event shape:
  { "event": "status", "step": "embedding", "message": "Generating AI embeddings..." }
  { "event": "status", "step": "scoring",   "message": "Computing match score..." }
  { "event": "result", "data": { ...AnalysisResponse } }
  { "event": "error",  "code": "EMBEDDING_ERROR", "message": "..." }

The client sends the resume file + job description as a JSON payload
AFTER the WebSocket connection is established:
  { "filename": "resume.pdf", "file_b64": "<base64>", "job_description": "..." }
"""
import asyncio
import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import AsyncSessionLocal
from ..models import MatchHistory, User
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

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])

# Step labels shown in the frontend stepper
STEP_MESSAGES = {
    "connected":      "Connected — waiting for file...",
    "extracting":     "Extracting resume text...",
    "embedding":      "Generating AI embeddings...",
    "scoring":        "Computing match score...",
    "gap_analysis":   "Analysing skill gaps...",
    "skill_resources":"Finding learning resources...",
    "building_resume":"Crafting your ATS resume...",
    "saving":         "Saving results...",
    "done":           "Analysis complete!",
}


@router.websocket("/analyze")
async def ws_analyze(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("WebSocket connection accepted from %s", websocket.client)

    # Browsers cannot set an Authorization header on a WebSocket handshake, so
    # the token arrives as a query parameter. Authenticate before doing any work
    # — otherwise this route is an unauthenticated way to spend AI quota and to
    # write history rows that belong to nobody.
    user_id = await _authenticate(websocket)
    if user_id is None:
        return

    async def send(event: str, **kwargs) -> None:
        """Send a JSON event to the client."""
        try:
            await websocket.send_json({"event": event, **kwargs})
        except Exception:
            pass  # Client may have disconnected

    async def status(step: str) -> None:
        await send("status", step=step, message=STEP_MESSAGES.get(step, step))

    try:
        await status("connected")

        # ── 1. Receive payload ────────────────────────────────────────────────
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            payload = json.loads(raw)
        except asyncio.TimeoutError:
            await send("error", code="TIMEOUT", message="No payload received within 60 seconds.")
            return
        except json.JSONDecodeError:
            await send("error", code="INVALID_PAYLOAD", message="Expected JSON payload.")
            return

        filename        = payload.get("filename", "resume")
        file_b64        = payload.get("file_b64", "")
        job_description = payload.get("job_description", "").strip()
        content_type    = payload.get("content_type", "application/octet-stream")

        # Validate
        if not file_b64:
            await send("error", code="EMPTY_FILE", message="No file data received.")
            return
        if len(job_description) < 50:
            await send("error", code="JD_TOO_SHORT",
                       message="Job description must be at least 50 characters.")
            return

        try:
            file_bytes = base64.b64decode(file_b64)
        except Exception:
            await send("error", code="DECODE_ERROR", message="Could not decode file data.")
            return

        if len(file_bytes) > settings.max_file_size_bytes:
            await send("error", code="FILE_TOO_LARGE",
                       message=f"File exceeds {settings.max_file_size_mb} MB limit.")
            return

        # ── 2. Extract text ───────────────────────────────────────────────────
        await status("extracting")
        try:
            resume_text = extract_text(file_bytes, filename, content_type)
        except Exception as exc:
            detail = getattr(exc, "detail", {})
            await send("error",
                       code=detail.get("code", "PARSE_ERROR") if isinstance(detail, dict) else "PARSE_ERROR",
                       message=detail.get("message", str(exc)) if isinstance(detail, dict) else str(exc))
            return

        # ── 3. Embeddings ─────────────────────────────────────────────────────
        await status("embedding")
        try:
            embeddings = await get_embeddings(resume_text, job_description)
        except Exception as exc:
            detail = getattr(exc, "detail", {})
            await send("error",
                       code=detail.get("code", "EMBEDDING_ERROR") if isinstance(detail, dict) else "EMBEDDING_ERROR",
                       message=detail.get("message", str(exc)) if isinstance(detail, dict) else str(exc))
            return

        # ── 4. Hybrid score ───────────────────────────────────────────────────
        await status("scoring")
        score = await calculate_hybrid_score(resume_text, job_description, embeddings)
        # Send score preview immediately so frontend can show it while rest continues
        await send("score_preview",
                   final=score.final,
                   semantic=score.semantic,
                   keyword=score.keyword)

        # ── 5. Gap analysis ───────────────────────────────────────────────────
        gap_report     = None
        resources_task = None

        if score.final < settings.gap_analysis_threshold:
            await status("gap_analysis")
            try:
                gap_report = await analyse_gap(
                    resume_text, job_description, score.missing_tokens, score.final
                )
                # Launch resources concurrently
                resources_task = asyncio.create_task(
                    find_skill_resources(gap_report.missing_skills)
                )
                await status("skill_resources")
            except Exception as exc:
                logger.warning("Gap analysis failed: %s", exc)
                # Non-fatal — continue without gap report

        # ── 6. ATS resume ─────────────────────────────────────────────────────
        await status("building_resume")
        try:
            ats_resume_md = await build_ats_resume(resume_text, job_description, filename)
        except Exception as exc:
            detail = getattr(exc, "detail", {})
            await send("error",
                       code=detail.get("code", "RESUME_BUILD_ERROR") if isinstance(detail, dict) else "RESUME_BUILD_ERROR",
                       message=detail.get("message", str(exc)) if isinstance(detail, dict) else str(exc))
            return

        # Collect resources
        if resources_task is not None:
            try:
                gap_report.skill_resources = await resources_task
            except Exception:
                gap_report.skill_resources = []

        # ── 7. Persist ────────────────────────────────────────────────────────
        await status("saving")
        async with AsyncSessionLocal() as db:
            history_row = MatchHistory(
                user_id=user_id,
                filename=filename,
                job_description_snippet=job_description[:500],
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
            await db.commit()

        # ── 8. Send final result ──────────────────────────────────────────────
        await status("done")

        response = AnalysisResponse(
            id=history_row.id,
            filename=filename,
            score_breakdown=ScoreBreakdown(
                semantic=score.semantic,
                keyword=score.keyword,
                final=score.final,
            ),
            gap_analysis=gap_report,
            ats_resume=ats_resume_md,
            created_at=history_row.created_at,
        )

        await send("result", data=response.model_dump(mode="json"))
        logger.info("WS analysis complete: id=%d score=%.1f", history_row.id, score.final)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error("Unexpected WS error: %s", exc, exc_info=True)
        msg = str(exc) if settings.is_development else "An unexpected error occurred."
        try:
            await send("error", code="INTERNAL_ERROR", message=msg)
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _authenticate(websocket: WebSocket) -> int | None:
    """Resolve ?token=... to a user id, closing the socket if it is not valid.

    Returns None when the caller has already been rejected.
    """
    import jwt

    from ..config import get_settings
    from ..database import AsyncSessionLocal

    settings = get_settings()
    token = websocket.query_params.get("token")

    async def reject(message: str) -> None:
        try:
            await websocket.send_json(
                {"event": "error", "code": "UNAUTHORIZED", "message": message}
            )
            # 1008 = policy violation, the closest WebSocket close code to 401.
            await websocket.close(code=1008)
        except Exception:
            pass

    if not token:
        await reject("Sign in to run an analysis.")
        return None

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        await reject("Your session has expired. Please sign in again.")
        return None
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        await reject("Invalid session. Please sign in again.")
        return None

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            await reject("Account not found or disabled.")
            return None

    return user_id
