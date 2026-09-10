"""Application settings, loaded from environment variables / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"

    # Control-plane database
    DATABASE_URL: str = "postgresql+asyncpg://genai:genai@127.0.0.1:5432/genai_dev"

    # Admin auth (JWT)
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption for provider/backend secrets (Fernet key — Fernet.generate_key())
    ENCRYPTION_KEY: str = ""

    # Where per-application SQLite-vec files live
    VECTOR_DATA_DIR: str = "./data/vectors"

    # Where cross-encoder models (RerankedRetrievalStrategy) are cached —
    # set as HF_HOME so they survive a container/process restart instead
    # of re-downloading from the Hugging Face Hub every time.
    RERANK_MODEL_CACHE_DIR: str = "./data/models"

    # Rate limiting default (requests per minute), per application unless overridden
    DEFAULT_RATE_LIMIT_PER_MINUTE: int = 120

    API_V1_PREFIX: str = "/api/v1"
    ADMIN_API_V1_PREFIX: str = "/admin/api/v1"

    def require_production_secrets(self) -> None:
        """Fail fast if critical secrets are missing outside development.

        Unlike a silent fallback to a throwaway key, this raises immediately
        at startup so a missing ENCRYPTION_KEY/JWT_SECRET_KEY is never
        discovered only after data has already been written under a key
        that won't survive a restart.
        """
        if self.ENVIRONMENT == "development":
            return
        missing = [
            name
            for name, value in (
                ("ENCRYPTION_KEY", self.ENCRYPTION_KEY),
                ("JWT_SECRET_KEY", self.JWT_SECRET_KEY),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required secrets for ENVIRONMENT={self.ENVIRONMENT!r}: "
                f"{', '.join(missing)}. Set them in .env before starting."
            )


settings = Settings()
