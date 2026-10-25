from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Project, ProjectMember, ProjectRole, User
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(creds.credentials) if creds else None
    user = await db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не авторизован")
    return user


async def get_membership(db: AsyncSession, project_id: int, user_id: int) -> ProjectMember | None:
    return await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )


def check_role(membership: ProjectMember | None, roles: tuple[ProjectRole, ...]) -> ProjectMember:
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Проект не найден или нет доступа")
    if roles and membership.role not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав для этого действия")
    return membership


def require_project_role(*roles: ProjectRole):
    """Зависимость для роутов с `{project_id}` в пути. Без аргументов — любой участник проекта."""

    async def dependency(
        project_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> ProjectMember:
        return check_role(await get_membership(db, project_id, user.id), roles)

    return dependency


# Готовые наборы ролей
ANY_MEMBER = require_project_role()
CAN_EDIT = require_project_role(ProjectRole.CAPTAIN, ProjectRole.MEMBER)
CAPTAIN_ONLY = require_project_role(ProjectRole.CAPTAIN)


async def fetch_project(db: AsyncSession, project_id: int) -> Project:
    # populate_existing перезагружает members, даже если проект уже в сессии
    project = await db.scalar(
        select(Project).where(Project.id == project_id).execution_options(populate_existing=True)
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Проект не найден")
    return project
