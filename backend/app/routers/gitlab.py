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
from app.deps import CAN_EDIT, CAPTAIN_ONLY, fetch_project
from app.models import Project, ProjectMember
from app.schemas import GitLabConnectIn, GitLabConnectOut, GitLabSyncOut
from app.services import review_service
from app.services.gitlab_service import (
    attach_repository,
    sync_issues_from_gitlab,
    sync_project,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gitlab"])


@router.put("/api/projects/{project_id}/gitlab/repository", response_model=GitLabConnectOut)
async def attach_gitlab_repository(
    project_id: int,
    data: GitLabConnectIn,
    _: ProjectMember = Depends(CAPTAIN_ONLY),
    db: AsyncSession = Depends(get_db),
):
    """Прикрепляет репозиторий, который капитан создал сам. Только CAPTAIN.

    Ссылка сохраняется, даже если GitLab сейчас недоступен — тогда `warning`
    объясняет, почему синхронизация задач пока не работает.
    """
    project = await fetch_project(db, project_id)
    try:
        warning = await attach_repository(db, project, data.repo_url)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
    return GitLabConnectOut(
        gitlab_project_id=project.gitlab_project_id,
        gitlab_repo_url=project.gitlab_repo_url,
        warning=warning,
    )


@router.delete("/api/projects/{project_id}/gitlab/repository", status_code=status.HTTP_204_NO_CONTENT)
async def detach_gitlab_repository(
    project_id: int,
    _: ProjectMember = Depends(CAPTAIN_ONLY),
    db: AsyncSession = Depends(get_db),
):
    """Открепляет репозиторий от проекта (сам репозиторий в GitLab не трогаем)."""
    project = await fetch_project(db, project_id)
    project.gitlab_project_id = None
    project.gitlab_repo_url = None
    await db.commit()


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
    if not project.gitlab_project_id and project.gitlab_repo_url:
        # Ссылку прикрепили, когда GitLab был недоступен — пробуем узнать ID сейчас
        warning = await attach_repository(db, project, project.gitlab_repo_url)
        if warning:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, warning)
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
    if x_gitlab_event == "Push Hook" and payload.get("ref"):
        # Push в ветку task-<id>-... запускает ИИ-ревью задачи
        background_tasks.add_task(
            review_service.on_push,
            gitlab_project_id,
            payload["ref"],
            payload.get("checkout_sha") or payload.get("after"),
        )
    return {"status": "accepted"}
