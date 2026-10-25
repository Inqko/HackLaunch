from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import ANY_MEMBER, CAN_EDIT
from app.models import ProjectMaterial, ProjectMember, ProjectRole
from app.schemas import MaterialCreate, MaterialOut

router = APIRouter(prefix="/api/projects/{project_id}/materials", tags=["materials"])


def material_out(m: ProjectMaterial, role: ProjectRole) -> MaterialOut:
    # edit_url никогда не уходит VIEWER-у: он получает только view_url
    can_edit = role in (ProjectRole.CAPTAIN, ProjectRole.MEMBER)
    return MaterialOut(
        id=m.id,
        title=m.title,
        type=m.type,
        target_url=m.edit_url if can_edit else m.view_url,
        access_mode="EDIT" if can_edit else "VIEW",
        can_edit=can_edit,
        created_at=m.created_at,
    )


@router.get("", response_model=list[MaterialOut])
async def list_materials(
    project_id: int, me: ProjectMember = Depends(ANY_MEMBER), db: AsyncSession = Depends(get_db)
):
    rows = await db.scalars(
        select(ProjectMaterial)
        .where(ProjectMaterial.project_id == project_id)
        .order_by(ProjectMaterial.created_at)
    )
    return [material_out(m, me.role) for m in rows]


@router.post("", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
async def create_material(
    project_id: int,
    data: MaterialCreate,
    me: ProjectMember = Depends(CAN_EDIT),
    db: AsyncSession = Depends(get_db),
):
    material = ProjectMaterial(project_id=project_id, created_by=me.user_id, **data.model_dump())
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material_out(material, me.role)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    project_id: int,
    material_id: int,
    _: ProjectMember = Depends(CAN_EDIT),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(ProjectMaterial, material_id)
    if material is None or material.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Материал не найден")
    await db.delete(material)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
