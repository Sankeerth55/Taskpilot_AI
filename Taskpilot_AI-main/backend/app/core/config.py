from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TaskPilot AI Backend"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./taskpilot.db"
    llm_provider: str = "gemini"
    llm_timeout_seconds: int = 30
    orchestration_timeout_seconds: int = 45
    # Read GEMINI_API_KEY directly from .env (no prefix)
    gemini_api_key: str = ""
    # Stable Gemini model — override via GEMINI_MODEL= in .env
    gemini_model: str = "auto"

    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            ".env.local",
            "backend/.env",
            "backend/.env.local",
            "Taskpilot_AI-main/backend/.env",
            "Taskpilot_AI-main/backend/.env.local",
        ),
        env_prefix="",  # No prefix so GEMINI_API_KEY and GEMINI_MODEL are read as-is
        extra="ignore",
    )


settings = Settings()

