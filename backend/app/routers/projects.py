from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import ANY_MEMBER, CAPTAIN_ONLY, fetch_project, get_current_user, get_membership
from app.models import Project, ProjectMember, ProjectRole, User
from app.schemas import (
    MemberAdd,
    MemberOut,
    MemberUpdate,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
)
from app.services.gitlab_service import (
    attach_repository,
    invite_to_gitlab,
    parse_repo_url,
    trigger_gitlab_repo_creation,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def member_out(m: ProjectMember) -> MemberOut:
    return MemberOut(
        user_id=m.user_id,
        name=m.user.name,
        email=m.user.email,
        gitlab_username=m.user.gitlab_username,
        role=m.role,
        specialization=m.specialization,
        joined_at=m.joined_at,
    )


def project_out(project: Project, my_role: ProjectRole) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        ai_progress_score=project.ai_progress_score,
        ai_health_status=project.ai_health_status,
        gitlab_repo_url=project.gitlab_repo_url,
        members_count=len(project.members),
        my_role=my_role,
        created_at=project.created_at,
    )


def project_detail(project: Project, my_role: ProjectRole) -> ProjectDetail:
    return ProjectDetail(
        **project_out(project, my_role).model_dump(),
        ai_health_summary=project.ai_health_summary,
        ai_risks=project.ai_risks or [],
        gitlab_project_id=project.gitlab_project_id,
        members=[member_out(m) for m in project.members],
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.created_at.desc())
    )
    return [project_out(p, role) for p, role in rows.all()]


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    repo_url = (data.gitlab_repo_url or "").strip()
    if repo_url:
        try:
            parse_repo_url(repo_url)  # плохую ссылку отклоняем до создания проекта
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None

    project = Project(name=data.name, description=data.description, created_by=user.id, ai_risks=[])
    project.members.append(
        ProjectMember(user_id=user.id, role=ProjectRole.CAPTAIN, specialization=data.specialization)
    )
    db.add(project)
    await db.commit()

    if repo_url:
        await attach_repository(db, project, repo_url)
    elif data.auto_create_gitlab:
        await trigger_gitlab_repo_creation(db, project, [user])

    return project_detail(await fetch_project(db, project.id), ProjectRole.CAPTAIN)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: int, membership: ProjectMember = Depends(ANY_MEMBER), db: AsyncSession = Depends(get_db)
):
    return project_detail(await fetch_project(db, project_id), membership.role)


@router.post("/{project_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: int,
    data: MemberAdd,
    _: ProjectMember = Depends(CAPTAIN_ONLY),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь с таким email не зарегистрирован")
    if await get_membership(db, project_id, user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь уже в проекте")

    member = ProjectMember(
        project_id=project_id, user_id=user.id, role=data.role, specialization=data.specialization
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    await invite_to_gitlab(await fetch_project(db, project_id), user)
    return member_out(member)


async def _get_target_member(db: AsyncSession, project_id: int, user_id: int) -> ProjectMember:
    target = await get_membership(db, project_id, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден")
    return target


@router.patch("/{project_id}/members/{user_id}", response_model=MemberOut)
async def update_member(
    project_id: int,
    user_id: int,
    data: MemberUpdate,
    me: ProjectMember = Depends(CAPTAIN_ONLY),
    db: AsyncSession = Depends(get_db),
):
    target = await _get_target_member(db, project_id, user_id)
    if target.user_id == me.user_id and data.role not in (None, ProjectRole.CAPTAIN):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя снять роль капитана с самого себя")
    if data.role is not None:
        target.role = data.role
    if data.specialization is not None:
        target.specialization = data.specialization
    await db.commit()
    await db.refresh(target)
    return member_out(target)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: int,
    user_id: int,
    me: ProjectMember = Depends(CAPTAIN_ONLY),
    db: AsyncSession = Depends(get_db),
):
    target = await _get_target_member(db, project_id, user_id)
    if target.user_id == me.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя удалить самого себя")
    await db.delete(target)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
