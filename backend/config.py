"""
Centralized settings management using pydantic-settings.
All config is loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str

    # ── AI Provider ───────────────────────────────────────────────────────────
    # "auto"     → Gemini if GEMINI_API_KEY is set, else Jina+Groq fallback
    # "gemini"   → force Gemini (requires GEMINI_API_KEY)
    # "fallback" → force Jina+Groq (requires JINA_API_KEY + GROQ_API_KEY)
    ai_provider: str = "auto"

    # Gemini (primary — paid)
    gemini_api_key: str = ""

    # Jina AI (free embeddings fallback — 1M tokens/month)
    jina_api_key: str = ""

    # Groq (free generation fallback)
    groq_api_key: str = ""

    # Groq retires hosted models on a rolling basis — llama-3.3-70b-versatile
    # was decommissioned and every request 503'd against a hardcoded name.
    # Overridable so a retirement is an env change, not a code change.
    # Current list: https://console.groq.com/docs/models
    groq_model: str = "openai/gpt-oss-120b"

    # Jina embedding model
    jina_model: str = "jina-embeddings-v3"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Security / Limits
    max_file_size_mb: int = 10
    max_resume_pages: int = 50
    max_jd_length: int = 20_000

    # Rate Limiting
    rate_limit_analyze: str = "10/minute"
    rate_limit_history: str = "30/minute"

    # App
    environment: str = "development"
    log_level: str = "INFO"

    # ── Auth ──────────────────────────────────────────────────────────────────
    # Signs the JWTs handed to the browser. MUST be overridden in production —
    # anyone holding this value can mint a token for any account.
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # a week; this is not a bank

    # ── Deployment ────────────────────────────────────────────────────────────
    # Hosts TrustedHostMiddleware will accept in production. Comma-separated.
    # MUST include this API's own public hostname (e.g. the *.onrender.com one),
    # otherwise health checks and direct API calls are rejected with 400.
    # "*" disables host checking entirely.
    allowed_hosts: str = "*"

    # Serve /docs + /redoc even outside development. Handy for a public demo.
    enable_docs: bool = True

    # SQLAlchemy pool sizing. Free-tier Postgres (Neon) and small dynos have a
    # low connection ceiling, so these default much lower than a real server.
    db_pool_size: int = 3
    db_max_overflow: int = 2

    # Scoring weights (must sum to 1.0)
    semantic_weight: float = 0.60
    keyword_weight: float = 0.40

    # Gap analysis threshold
    gap_analysis_threshold: float = 85.0

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
