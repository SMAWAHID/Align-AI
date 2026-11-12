"""
Async SQLAlchemy 2.0 engine + session factory.
Uses asyncpg driver for PostgreSQL.
"""
from typing import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()


# ── DSN normalisation ─────────────────────────────────────────────────────────
# Managed Postgres providers (Neon, Supabase, Render, Railway) hand out a libpq
# style URL:
#
#   postgresql://user:pass@host/db?sslmode=require&channel_binding=require
#
# asyncpg is not libpq: it neither understands the "postgresql://" driver alias
# SQLAlchemy needs, nor the sslmode/channel_binding query parameters, and passing
# them straight through raises TypeError at connect time. Rewriting the URL here
# means the provider's copy-paste string works unmodified.

_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "sslrootcert", "sslcert", "sslkey"}


def _normalize_database_url(raw: str) -> tuple[str, dict]:
    """Return an asyncpg-compatible URL plus the connect_args it implies."""
    url = urlsplit(raw.strip())
    connect_args: dict = {}

    # postgres:// and postgresql:// → postgresql+asyncpg://
    scheme = url.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"

    kept, ssl_requested = [], False
    for key, value in parse_qsl(url.query, keep_blank_values=True):
        if key.lower() == "sslmode":
            # disable/allow/prefer → plaintext is acceptable; anything else → TLS
            ssl_requested = value.lower() not in ("disable", "allow", "prefer")
        elif key.lower() in _LIBPQ_ONLY_PARAMS:
            continue  # silently drop — asyncpg has no equivalent
        else:
            kept.append((key, value))

    # Every managed provider requires TLS; default to on unless explicitly off.
    if ssl_requested or "sslmode" not in raw.lower():
        if url.hostname not in ("localhost", "127.0.0.1", "::1", None):
            connect_args["ssl"] = "require"

    # Connection poolers (Neon's "-pooler" endpoint, Supabase's pgbouncer) do not
    # support the server-side prepared statements asyncpg caches by default, and
    # fail with "prepared statement _asyncpg_stmt_x already exists". Disabling the
    # cache costs almost nothing here and makes either endpoint work.
    connect_args["statement_cache_size"] = 0

    return urlunsplit((scheme, url.netloc, url.path, urlencode(kept), url.fragment)), connect_args


DATABASE_URL, _CONNECT_ARGS = _normalize_database_url(settings.database_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.is_development,
    # Free-tier Postgres caps concurrent connections well below a real server,
    # so these are sized from config rather than hardcoded at 10/20.
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,          # Validates connections before use
    pool_recycle=300,            # Serverless Postgres drops idle conns early
    connect_args=_CONNECT_ARGS,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Base.metadata.create_all only creates MISSING tables — it never alters an
# existing one. Columns added to a model after its table already exists in a
# deployed database therefore need an explicit, idempotent statement here.
_MIGRATIONS: tuple[str, ...] = (
    # Ownership, added when accounts were introduced. Existing rows predate any
    # user and stay NULL rather than being deleted.
    """
    ALTER TABLE match_history
        ADD COLUMN IF NOT EXISTS user_id INTEGER
        REFERENCES users(id) ON DELETE CASCADE
    """,
    "CREATE INDEX IF NOT EXISTS ix_match_history_user_id ON match_history (user_id)",
)


async def init_db() -> None:
    """Create tables and apply column migrations on startup (idempotent)."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        # Import models so Base.metadata is populated
        from . import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
        for statement in _MIGRATIONS:
            await conn.execute(text(statement))


async def dispose_db() -> None:
    """Dispose engine connection pool on shutdown."""
    await engine.dispose()
