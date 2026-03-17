import os
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Meal Planner"
    API_V1_STR: str = "/api/v1"

    # Environment: development, staging, production
    ENVIRONMENT: str = "development"

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
    USE_SQLITE_LOCAL: bool = False

    # Sentry
    SENTRY_DSN: str | None = None

    # FatSecret API
    FATSECRET_API_KEY: str | None = None
    FATSECRET_API_SECRET: str | None = None

    # Edamam API
    EDAMAM_APP_ID: str | None = None
    EDAMAM_APP_KEY: str | None = None

    # Auth
    SECRET_KEY: str = "a_very_secret_key"
    ENCRYPTION_KEY: str = "VQZJVhu2seQqq4ZOM_KlwxbqOE0WOf1070WURHeJABQ="
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Scraping
    SCRAPING_CONCURRENCY: int = 3
    DEFAULT_POSTAL_CODE: str = "H4T1V6"
    SUPPORTED_STORES: list[str] = [
        "metro",
        "walmart",
        "maxi",
        "provigo",
        "iga",
        "super_c",
        "adonis",
        "costco",
    ]
    WEBHOOK_URL: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @model_validator(mode='after')
    def validate_settings(self) -> 'Settings':
        # Check for OpenRouter API key if not using mock AI
        if not self.USE_MOCK_AI and not self.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY must be set when USE_MOCK_AI is False.")

        # Check for default secret key in production/staging environments
        if self.ENVIRONMENT in ["production", "staging"] and self.SECRET_KEY == "a_very_secret_key":
            raise ValueError("Default SECRET_KEY is not allowed in production or staging environments. Please generate a new one.")

        # Check for default encryption key in production/staging environments
        if self.ENVIRONMENT in ["production", "staging"] and self.ENCRYPTION_KEY == "VQZJVhu2seQqq4ZOM_KlwxbqOE0WOf1070WURHeJABQ=":
            raise ValueError("Default ENCRYPTION_KEY is not allowed in production or staging environments. Please generate a new one.")

        return self

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # If running in Docker (implied by default values being set to 'db'), construct postgres URL
        # But we need a way to detect if we want local sqlite fallback for dev without docker
        if self.USE_SQLITE_LOCAL:
             return "sqlite:///./local_dev.db"

        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
