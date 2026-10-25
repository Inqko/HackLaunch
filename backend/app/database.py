from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _apply_light_migrations(conn) -> None:
    """Догоняем схему существующей БД без Alembic (каркас).

    create_all не умеет добавлять колонки в уже созданную таблицу, поэтому
    для старых dev-баз аккуратно добавляем nullable-колонку и уникальный индекс.
    """
    inspector = inspect(conn)
    if "tasks" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "gitlab_issue_iid" not in columns:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN gitlab_issue_iid INTEGER"))
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_tasks_project_gitlab_iid "
            "ON tasks (project_id, gitlab_issue_iid)"
        )
    )


async def _ensure_schema(conn) -> None:
    """Лёгкая миграция для каркаса: create_all не меняет существующие таблицы."""
    dialect = conn.dialect.name
    if dialect == "sqlite":
        cols = (await conn.exec_driver_sql("PRAGMA table_info(users)")).all()
        names = {row[1] for row in cols}
        if "avatar_url" not in names:
            await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512)")
    elif dialect == "postgresql":
        await conn.exec_driver_sql(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512)"
        )


async def init_db() -> None:
    # Для каркаса таблицы создаются на старте; Alembic можно подключить позже
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_light_migrations)
        await _ensure_schema(conn)
