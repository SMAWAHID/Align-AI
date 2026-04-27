"""
AlignAI FastAPI Application
Entry: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import get_settings
from .database import dispose_db, init_db
from .routers import analysis_router, ws_router, history_router, resume_router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger("alignai")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AlignAI — Semantic Resume Matcher",
    version="1.0.0",
    docs_url="/docs"        if settings.is_development else None,
    redoc_url="/redoc"      if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-Request-ID"],
    max_age=86400,
)

if not settings.is_development:
    from urllib.parse import urlparse
    trusted = [urlparse(o).hostname for o in settings.allowed_origins_list if o]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted)


@app.middleware("http")
async def request_timing(request: Request, call_next) -> Response:
    start = time.perf_counter()
    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.1f}ms"
    if elapsed_ms > 10_000:
        logger.warning("Slow request: %s %s took %.0fms",
                       request.method, request.url.path, elapsed_ms)
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response: Response = await call_next(request)
    response.headers.update({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options":        "DENY",
        "X-XSS-Protection":       "1; mode=block",
        "Referrer-Policy":        "strict-origin-when-cross-origin",
        "Cache-Control":          "no-store",
    })
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s",
                 request.method, request.url.path, exc, exc_info=True)
    message = str(exc) if settings.is_development else "An unexpected server error occurred."
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "INTERNAL_ERROR", "message": message}},
    )


@app.on_event("startup")
async def startup() -> None:
    logger.info("AlignAI starting up (env=%s)", settings.environment)
    await init_db()
    logger.info("Database tables initialised")


@app.on_event("shutdown")
async def shutdown() -> None:
    await dispose_db()


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", tags=["meta"], include_in_schema=False)
async def root() -> dict:
    return {"message": "AlignAI API — see /docs for usage."}


# Register all routers
app.include_router(analysis_router)   # POST /api/v1/analyze (HTTP fallback)
app.include_router(ws_router)         # WS   /api/v1/ws/analyze
app.include_router(history_router)
app.include_router(resume_router)
