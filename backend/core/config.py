import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent


def load_env_files(
    backend_env: Optional[Path] = None,
    root_env: Optional[Path] = None,
) -> None:
    """Load backend/.env, then the repo-root .env for any still-missing keys.

    Existing process environment variables always win (CI, exports, pytest).
    Interpolation is off so passwords may contain `$`.
    """
    load_dotenv(
        backend_env or (_BACKEND_DIR / ".env"),
        override=False,
        interpolate=False,
        encoding="utf-8",
    )
    load_dotenv(
        root_env or (_REPO_ROOT / ".env"),
        override=False,
        interpolate=False,
        encoding="utf-8",
    )


load_env_files()


class Settings(BaseModel):
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://app_user:change-me@localhost:5432/postgres"
    )
    DATABASE_ADMIN_URL: str = os.getenv("DATABASE_ADMIN_URL", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://localhost:8080,http://127.0.0.1:8080",
    )
    AI_BUDGET_SECONDS: float = float(os.getenv("AI_BUDGET_SECONDS", "8"))
    AI_CACHE_TTL_SECONDS: int = int(os.getenv("AI_CACHE_TTL_SECONDS", "60"))
    AI_NARRATIVE_ENABLED: bool = os.getenv("AI_NARRATIVE_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    def require_jwt_secret(self) -> str:
        if self.JWT_SECRET:
            return self.JWT_SECRET
        if self.APP_ENV == "production":
            raise RuntimeError("JWT_SECRET must be set in production")
        return "dev-only-not-for-production"


settings = Settings()
