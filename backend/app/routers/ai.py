from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import CAN_EDIT, CAPTAIN_ONLY, fetch_project
from app.models import ProjectMember
from app.schemas import AIStatusOut, GenerateTasksIn, TaskOut
from app.services.ai_service import generate_task_drafts, refresh_project_health

router = APIRouter(prefix="/api/projects/{project_id}/ai", tags=["ai"])


@router.post("/generate-tasks", response_model=list[TaskOut])
async def generate_tasks(
    project_id: int,
    data: GenerateTasksIn,
    _: ProjectMember = Depends(CAPTAIN_ONLY),
    db: AsyncSession = Depends(get_db),
):
    project = await fetch_project(db, project_id)
    return await generate_task_drafts(db, project, data.additional_context)


@router.post("/refresh-status", response_model=AIStatusOut)
async def refresh_status(
    project_id: int, _: ProjectMember = Depends(CAN_EDIT), db: AsyncSession = Depends(get_db)
):
    project = await refresh_project_health(db, await fetch_project(db, project_id))
    return AIStatusOut(
        ai_health_summary=project.ai_health_summary,
        ai_health_status=project.ai_health_status,
        ai_progress_score=project.ai_progress_score,
        ai_risks=project.ai_risks or [],
    )
