import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Meal Planner"
    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "mealplanner"

    # Fallback to SQLite if DATABASE_URL not set
    DATABASE_URL: str | None = None

    # AI
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    FALLBACK_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    OPENROUTER_MODEL: str = "anthropic/claude-3.5-sonnet" # Keeping for backward compat if any

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # App Mode
    USE_MOCK_AI: bool = False

    # Sentry
    SENTRY_DSN: str | None = None

    # FatSecret API
    FATSECRET_API_KEY: str | None = None
    FATSECRET_API_SECRET: str | None = None

    # Auth
    SECRET_KEY: str = "a_very_secret_key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # If running in Docker (implied by default values being set to 'db'), construct postgres URL
        # But we need a way to detect if we want local sqlite fallback for dev without docker
        if os.getenv("USE_SQLITE_LOCAL", "False").lower() == "true":
             return "sqlite:///./local_dev.db"

        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
