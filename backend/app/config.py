from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "sqlite+aiosqlite:///./hacklaunch.db"

    jwt_secret: str = "dev-secret-change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    cors_origins: list[str] = ["http://localhost:5173"]

    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str = ""
    gitlab_namespace_id: int | None = None
    use_mock_gitlab: bool = True

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"


settings = Settings()
