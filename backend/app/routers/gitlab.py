"""GitLab: ручная синхронизация задач и приём вебхуков (Участник 3)."""

import logging
import secrets

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SessionLocal, get_db
from app.deps import CAN_EDIT, fetch_project
from app.models import Project, ProjectMember
from app.schemas import GitLabSyncOut
from app.services.gitlab_service import sync_issues_from_gitlab, sync_project

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gitlab"])


@router.post("/api/projects/{project_id}/gitlab/sync", response_model=GitLabSyncOut)
async def sync_gitlab(
    project_id: int,
    _: ProjectMember = Depends(CAN_EDIT),
    db: AsyncSession = Depends(get_db),
):
    """Полная синхронизация: приглашает участников и импортирует issues.

    Доступна CAPTAIN/MEMBER. Ошибки GitLab отдаются как 502, чтобы фронт
    мог показать понятное сообщение, а не 500.
    """
    project = await fetch_project(db, project_id)
    if not project.gitlab_project_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "У проекта нет GitLab-репозитория"
        )
    try:
        result = await sync_project(db, project)
    except Exception:
        logger.exception("GitLab sync failed for project %s", project_id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Не удалось синхронизироваться с GitLab"
        ) from None
    return GitLabSyncOut(**result)


async def _sync_issues_in_background(project_id: int) -> None:
    """Вебхук не должен блокировать GitLab, поэтому импорт идёт в фоне.

    Участников на каждый push не приглашаем: это уже делает add_member,
    а полная синхронизация доступна кнопкой/эндпоинтом.
    """
    async with SessionLocal() as db:
        project = await db.get(Project, project_id)
        if project is None or not project.gitlab_project_id:
            return
        try:
            await sync_issues_from_gitlab(db, project)
        except Exception:
            await db.rollback()
            logger.exception("GitLab webhook sync failed for project %s", project_id)


@router.post("/api/webhooks/gitlab", status_code=status.HTTP_202_ACCEPTED)
async def gitlab_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitlab_token: str | None = Header(default=None),
    x_gitlab_event: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Приёмник вебхуков GitLab (Push Hook / Issue Hook).

    GitLab присылает секрет в X-Gitlab-Token; без настроенного секрета
    эндпоинт выключен (503), чтобы случайно не открыть запись в БД.
    """
    if not settings.gitlab_webhook_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "GitLab webhook secret is not configured",
        )
    if not x_gitlab_token or not secrets.compare_digest(
        x_gitlab_token, settings.gitlab_webhook_secret
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid GitLab webhook token")

    if x_gitlab_event not in {"Push Hook", "Issue Hook"}:
        return {"status": "ignored"}

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid JSON payload"
        ) from None
    raw_project_id = payload.get("project_id") or (payload.get("project") or {}).get("id")
    try:
        gitlab_project_id = int(raw_project_id)
    except (TypeError, ValueError):
        return {"status": "ignored"}

    project = await db.scalar(
        select(Project).where(Project.gitlab_project_id == gitlab_project_id)
    )
    if project is None:
        return {"status": "ignored"}

    background_tasks.add_task(_sync_issues_in_background, project.id)
    return {"status": "accepted"}
