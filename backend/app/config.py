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

    # auto: DeepSeek, если задан ключ, иначе Gemini, иначе фоллбэк без ИИ
    ai_provider: str = "auto"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    # Для self-hosted/vLLM провайдеров: отключает «размышления» reasoning-модели, ответ в разы быстрее
    deepseek_disable_thinking: bool = False

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    # ИИ-ревью: как часто проверять ветки задач на новые коммиты (0 — выключить опрос;
    # с вебхуком GitLab или кнопкой «На ревью» опрос не обязателен)
    review_poll_seconds: int = 60

    password_code_ttl_minutes: int = 10

    # SMTP для писем с кодом подтверждения. Без SMTP_HOST код пишется в лог,
    # а при EMAIL_DEBUG=true дополнительно возвращается в ответе API (только для разработки).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@hacklaunch.local"
    smtp_use_tls: bool = True
    email_debug: bool = True

    # Загрузка файлов (аватары)
    upload_dir: str = "uploads"
    avatar_max_mb: int = 5


settings = Settings()
