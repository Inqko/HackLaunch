from typing import Literal

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import ANY_MEMBER, fetch_project
from app.models import ProjectMember
from app.schemas import AnalyticsOut
from app.services.analytics_service import analytics_to_csv, build_analytics

router = APIRouter(prefix="/api/projects/{project_id}/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
async def get_analytics(project_id: int, _: ProjectMember = Depends(ANY_MEMBER), db: AsyncSession = Depends(get_db)):
    return await build_analytics(db, await fetch_project(db, project_id))


@router.get("/export")
async def export_analytics(
    project_id: int,
    format: Literal["csv", "json"] = "csv",
    _: ProjectMember = Depends(ANY_MEMBER),
    db: AsyncSession = Depends(get_db),
):
    data = await build_analytics(db, await fetch_project(db, project_id))
    filename = f"analytics-project-{project_id}.{format}"
    if format == "csv":
        content, media_type = analytics_to_csv(data), "text/csv; charset=utf-8"
    else:
        content, media_type = data.model_dump_json(indent=2), "application/json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
