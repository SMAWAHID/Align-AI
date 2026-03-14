"""
Centralized settings management using pydantic-settings.
All config is loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="backend/.env",
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

    # Groq (free generation fallback — llama-3.3-70b-versatile)
    groq_api_key: str = ""

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

    # Scoring weights (must sum to 1.0)
    semantic_weight: float = 0.60
    keyword_weight: float = 0.40

    # Gap analysis threshold
    gap_analysis_threshold: float = 85.0

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
