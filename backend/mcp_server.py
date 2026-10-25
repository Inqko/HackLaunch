"""MCP-сервер HackLaunch AI (Участник 2).

Подключает внешних ИИ-ассистентов (Claude Desktop, Cursor и т.д.) напрямую к БД платформы.
Запуск: `python mcp_server.py` (stdio). Пример конфига — в README.
"""

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.deps import fetch_project
from app.models import Task, TaskPriority, TaskStatus
from app.schemas import TaskOut
from app.services.ai_service import compute_progress, generate_task_drafts
from app.services.gitlab_service import sync_task_to_gitlab

mcp = FastMCP("HackLaunch AI")


def _task_dict(t: Task) -> dict:
    return TaskOut.model_validate(t).model_dump(mode="json")


@mcp.tool()
async def generate_tasks_from_prompt(project_id: int, prompt: str) -> list[dict]:
    """Создает черновики задач (AI_DRAFT) по текстовому описанию функционала.
    Черновики появятся у Капитана на экране утверждения."""
    await init_db()
    async with SessionLocal() as db:
        project = await fetch_project(db, project_id)
        return [_task_dict(t) for t in await generate_task_drafts(db, project, prompt)]


@mcp.tool()
async def get_project_health(project_id: int) -> dict:
    """Возвращает статус проекта, прогресс, риски, участников и список задач."""
    await init_db()
    async with SessionLocal() as db:
        project = await fetch_project(db, project_id)
        tasks = list(await db.scalars(select(Task).where(Task.project_id == project_id)))
        return {
            "name": project.name,
            "health_status": project.ai_health_status.value,
            "summary": project.ai_health_summary,
            "progress": compute_progress([t for t in tasks if t.status != TaskStatus.AI_DRAFT]),
            "risks": project.ai_risks or [],
            "members": [
                {"user_id": m.user_id, "name": m.user.name, "role": m.role.value,
                 "specialization": m.specialization.value}
                for m in project.members
            ],
            "tasks": [_task_dict(t) for t in tasks],
        }


@mcp.tool()
async def create_single_task(
    project_id: int, title: str, assignee_name: str | None = None, priority: str = "MEDIUM",
    estimated_hours: float = 1.0, description: str | None = None,
) -> dict:
    """Создает одну задачу в статусе TODO. assignee_name — имя участника (поиск без учета регистра)."""
    await init_db()
    async with SessionLocal() as db:
        project = await fetch_project(db, project_id)
        assignee_id = None
        if assignee_name:
            match = [m for m in project.members if assignee_name.lower() in m.user.name.lower()]
            if not match:
                raise ValueError(f"Участник '{assignee_name}' не найден в проекте")
            assignee_id = match[0].user_id
        task = Task(
            project_id=project_id, title=title, description=description, assignee_id=assignee_id,
            priority=TaskPriority(priority.upper()), estimated_hours=estimated_hours, status=TaskStatus.TODO,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        await sync_task_to_gitlab(db, task)
        return _task_dict(task)


@mcp.tool()
async def assign_task(task_id: int, user_id: int) -> dict:
    """Назначает задачу участнику проекта."""
    await init_db()
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if task is None:
            raise ValueError("Задача не найдена")
        project = await fetch_project(db, task.project_id)
        if user_id not in {m.user_id for m in project.members}:
            raise ValueError("Пользователь не участник проекта")
        task.assignee_id = user_id
        await db.commit()
        await db.refresh(task)
        await sync_task_to_gitlab(db, task)
        return _task_dict(task)


@mcp.tool()
async def update_task_status(task_id: int, new_status: str) -> dict:
    """Переводит задачу в статус TODO / IN_PROGRESS / REVIEW / DONE."""
    await init_db()
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if task is None:
            raise ValueError("Задача не найдена")
        status = TaskStatus(new_status.upper())
        if status == TaskStatus.AI_DRAFT:
            raise ValueError("Нельзя вернуть задачу в черновики")
        task.status = status
        await db.commit()
        await db.refresh(task)
        await sync_task_to_gitlab(db, task)
        return _task_dict(task)


if __name__ == "__main__":
    mcp.run()
