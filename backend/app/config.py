from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env.shared — общие настройки команды (может лежать в git),
    # .env — локальные переопределения и секреты (в .gitignore).
    model_config = SettingsConfigDict(
        env_file=(".env.shared", ".env"), extra="ignore", env_ignore_empty=True
    )

    database_url: str = "sqlite+aiosqlite:///./hacklaunch.db"

    jwt_secret: str = "dev-secret-change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    cors_origins: list[str] = ["http://localhost:5173"]

    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str = ""
    gitlab_namespace_id: int | None = None
    use_mock_gitlab: bool = True
    # Мост задач и issues GitLab. Пустые значения отключают вебхуки/синхронизацию.
    gitlab_webhook_url: str = ""
    gitlab_webhook_secret: str = ""
    gitlab_task_label: str = "hacklaunch"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"


settings = Settings()
