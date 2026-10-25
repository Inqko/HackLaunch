"""ИИ-ревью задач: отправка на ревью, история, решение капитана."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import check_role, get_current_user, get_membership
from app.models import Project, ProjectMember, ProjectRole, ReviewState, Task, TaskReview, TaskStatus, User
from app.schemas import ReviewRejectIn, TaskOut, TaskReviewOut, TaskReviewsOut
from app.services import review_service

router = APIRouter(prefix="/api/tasks/{task_id}", tags=["review"])


async def _load(
    db: AsyncSession, task_id: int, user: User, roles: tuple[ProjectRole, ...]
) -> tuple[Task, Project, ProjectMember]:
    task = await db.get(Task, task_id)
    if task is None or task.status == TaskStatus.AI_DRAFT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
    member = check_role(await get_membership(db, task.project_id, user.id), roles)
    return task, await db.get(Project, task.project_id), member


@router.post("/review/submit", response_model=TaskOut)
async def submit_for_review(
    task_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Участник запушил код — отправить задачу на ИИ-ревью (то же делают вебхук и опрос веток)."""
    task, project, me = await _load(db, task_id, user, (ProjectRole.CAPTAIN, ProjectRole.MEMBER))
    if me.role != ProjectRole.CAPTAIN and task.assignee_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Отправить на ревью можно только свою задачу")
    if not project.gitlab_project_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Для ИИ-ревью нужен GitLab-репозиторий: капитан прикрепляет его в шапке проекта",
        )
    if task.status != TaskStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "На ревью отправляется задача в статусе «В работе»")
    await review_service.start_review(db, task)
    await db.refresh(task)
    return task


@router.get("/reviews", response_model=TaskReviewsOut)
async def list_reviews(task_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    task, project, _ = await _load(db, task_id, user, ())
    reviews = await db.scalars(
        select(TaskReview).where(TaskReview.task_id == task_id).order_by(TaskReview.id.desc())
    )
    return TaskReviewsOut(
        task=TaskOut.model_validate(task),
        mr_url=review_service.mr_url(project, task),
        reviews=[TaskReviewOut.model_validate(r) for r in reviews],
    )


def _require_awaiting(task: Task) -> None:
    if task.review_state != ReviewState.AWAITING_CAPTAIN or not task.gitlab_mr_iid:
        raise HTTPException(status.HTTP_409_CONFLICT, "Задача не ждет решения капитана")


@router.post("/review/approve", response_model=TaskOut)
async def approve_review(task_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Капитан согласен: MR вливается в основную ветку, задача — «Готово»."""
    task, project, _ = await _load(db, task_id, user, (ProjectRole.CAPTAIN,))
    _require_awaiting(task)
    try:
        await review_service.captain_approve(db, task, project, user.id)
    except review_service.MergeError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "GitLab недоступен, попробуйте еще раз") from None
    await db.refresh(task)
    return task


@router.post("/review/reject", response_model=TaskOut)
async def reject_review(
    task_id: int, data: ReviewRejectIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Капитан не согласен: комментарий участнику, задача обратно «В работе»."""
    task, project, _ = await _load(db, task_id, user, (ProjectRole.CAPTAIN,))
    _require_awaiting(task)
    await review_service.captain_reject(db, task, project, user.id, data.comment)
    await db.refresh(task)
    return task
