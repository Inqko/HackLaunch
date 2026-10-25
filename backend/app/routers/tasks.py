from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import ANY_MEMBER, CAN_EDIT, CAPTAIN_ONLY, check_role, fetch_project, get_current_user, get_membership
from app.models import ProjectMember, ProjectRole, Task, TaskStatus, User
from app.schemas import (
    ApproveBatchIn,
    ApproveBatchOut,
    DraftGroup,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.services.ai_service import compute_progress

router = APIRouter(prefix="/api", tags=["tasks"])


async def ensure_assignee(db: AsyncSession, project_id: int, assignee_id: int | None) -> None:
    if assignee_id is None:
        return
    m = await get_membership(db, project_id, assignee_id)
    if m is None or m.role == ProjectRole.VIEWER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Исполнитель должен быть участником проекта")


async def active_tasks(db: AsyncSession, project_id: int, assignee_id: int | None = None) -> list[Task]:
    stmt = select(Task).where(Task.project_id == project_id, Task.status != TaskStatus.AI_DRAFT)
    if assignee_id is not None:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    return list(await db.scalars(stmt.order_by(Task.created_at)))


async def update_progress(db: AsyncSession, project_id: int) -> None:
    # Дешевый пересчет процента без вызова LLM — полный анализ через /ai/refresh-status
    project = await fetch_project(db, project_id)
    project.ai_progress_score = compute_progress(await active_tasks(db, project_id))
    await db.commit()


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks(project_id: int, _: ProjectMember = Depends(ANY_MEMBER), db: AsyncSession = Depends(get_db)):
    return await active_tasks(db, project_id)


@router.get("/projects/{project_id}/tasks/my", response_model=list[TaskOut])
async def my_tasks(project_id: int, me: ProjectMember = Depends(ANY_MEMBER), db: AsyncSession = Depends(get_db)):
    return await active_tasks(db, project_id, assignee_id=me.user_id)


@router.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: int, data: TaskCreate, _: ProjectMember = Depends(CAN_EDIT), db: AsyncSession = Depends(get_db)
):
    await ensure_assignee(db, project_id, data.assignee_id)
    task = Task(project_id=project_id, status=TaskStatus.TODO, **data.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await update_progress(db, project_id)
    return task


@router.get("/projects/{project_id}/tasks/drafts", response_model=list[DraftGroup])
async def list_drafts(project_id: int, _: ProjectMember = Depends(CAPTAIN_ONLY), db: AsyncSession = Depends(get_db)):
    project = await fetch_project(db, project_id)
    drafts = await db.scalars(
        select(Task).where(Task.project_id == project_id, Task.status == TaskStatus.AI_DRAFT).order_by(Task.id)
    )
    members = {m.user_id: m for m in project.members}
    groups: dict[int | None, DraftGroup] = {}
    for t in drafts:
        m = members.get(t.assignee_id)
        group = groups.setdefault(t.assignee_id, DraftGroup(
            assignee_id=t.assignee_id,
            assignee_name=m.user.name if m else "Не назначено",
            specialization=m.specialization if m else None,
            tasks=[],
        ))
        group.tasks.append(TaskOut.model_validate(t))
    return list(groups.values())


@router.post("/projects/{project_id}/tasks/approve-batch", response_model=ApproveBatchOut)
async def approve_batch(
    project_id: int, data: ApproveBatchIn, _: ProjectMember = Depends(CAPTAIN_ONLY), db: AsyncSession = Depends(get_db)
):
    drafts = {
        t.id: t
        for t in await db.scalars(
            select(Task).where(Task.project_id == project_id, Task.status == TaskStatus.AI_DRAFT)
        )
    }
    approved: list[Task] = []
    for item in data.approved_tasks:
        await ensure_assignee(db, project_id, item.assignee_id)
        if item.id is None:
            task = Task(project_id=project_id, created_by_ai=False)
            db.add(task)
        elif item.id in drafts:
            task = drafts[item.id]
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Черновик {item.id} не найден")
        task.title = item.title
        task.description = item.description
        task.assignee_id = item.assignee_id
        task.priority = item.priority
        task.estimated_hours = item.estimated_hours
        task.status = TaskStatus.TODO
        approved.append(task)

    rejected = 0
    for task_id in data.rejected_task_ids:
        if task_id in drafts:
            await db.delete(drafts[task_id])
            rejected += 1

    await db.commit()
    for t in approved:
        await db.refresh(t)
    await update_progress(db, project_id)
    return ApproveBatchOut(approved=[TaskOut.model_validate(t) for t in approved], rejected_count=rejected)


async def _task_with_access(db: AsyncSession, task_id: int, user: User) -> Task:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
    roles = (ProjectRole.CAPTAIN,) if task.status == TaskStatus.AI_DRAFT else (ProjectRole.CAPTAIN, ProjectRole.MEMBER)
    check_role(await get_membership(db, task.project_id, user.id), roles)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int, data: TaskUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    task = await _task_with_access(db, task_id, user)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("status") == TaskStatus.AI_DRAFT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя вернуть задачу в черновики")
    if "assignee_id" in changes:
        await ensure_assignee(db, task.project_id, changes["assignee_id"])
    for field, value in changes.items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    if "status" in changes or "estimated_hours" in changes:
        await update_progress(db, task.project_id)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    task = await _task_with_access(db, task_id, user)
    project_id = task.project_id
    await db.delete(task)
    await db.commit()
    await update_progress(db, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
