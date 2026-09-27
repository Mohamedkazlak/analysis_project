import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-use-32b")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://app_user:change-me@localhost:5432/postgres"
)
os.environ["AI_NARRATIVE_ENABLED"] = "false"
