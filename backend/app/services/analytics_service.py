"""Аналитика: задачи из БД + коммиты/MR из GitLab (Участник 3)."""

import csv
import io
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectRole, Task, TaskStatus
from app.schemas import AnalyticsOut, MemberStats
from app.services.gitlab_service import ContributorStats, get_gitlab_client

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    ("name", "Участник"),
    ("role", "Роль"),
    ("specialization", "Специализация"),
    ("tasks_assigned", "Задач назначено"),
    ("tasks_in_progress", "В работе"),
    ("tasks_completed", "Выполнено"),
    ("hours_completed", "Закрыто часов"),
    ("gitlab_commits", "Коммиты"),
    ("gitlab_mrs", "Merge Requests"),
    ("last_activity", "Последняя активность"),
    ("contribution_percent", "Вклад, %"),
]


def _score(tasks_completed: int, hours: float, commits: int, mrs: int) -> float:
    return tasks_completed * 2 + hours + commits * 0.5 + mrs * 2


async def build_analytics(db: AsyncSession, project: Project) -> AnalyticsOut:
    tasks = list(await db.scalars(
        select(Task).where(Task.project_id == project.id, Task.status != TaskStatus.AI_DRAFT)
    ))
    members = [m for m in project.members if m.role != ProjectRole.VIEWER]

    gitlab: dict[int, ContributorStats] = {}
    if project.gitlab_project_id:
        try:
            gitlab = await get_gitlab_client().get_contributor_stats(
                project.gitlab_project_id, [m.user for m in members]
            )
        except Exception:
            logger.exception("GitLab stats failed for project %s", project.id)

    rows = []
    for m in members:
        mine = [t for t in tasks if t.assignee_id == m.user_id]
        done = [t for t in mine if t.status == TaskStatus.DONE]
        gl = gitlab.get(m.user_id, ContributorStats())
        rows.append(MemberStats(
            user_id=m.user_id,
            name=m.user.name,
            role=m.role,
            specialization=m.specialization,
            tasks_assigned=len(mine),
            tasks_in_progress=sum(t.status == TaskStatus.IN_PROGRESS for t in mine),
            tasks_completed=len(done),
            hours_completed=sum(t.estimated_hours for t in done),
            gitlab_commits=gl.commits,
            gitlab_mrs=gl.mrs,
            last_activity=gl.last_activity,
            contribution_percent=0.0,
        ))

    scores = [_score(r.tasks_completed, r.hours_completed, r.gitlab_commits, r.gitlab_mrs) for r in rows]
    total_score = sum(scores)
    for r, s in zip(rows, scores):
        r.contribution_percent = round(100 * s / total_score, 1) if total_score else 0.0

    return AnalyticsOut(
        project_id=project.id,
        total_tasks=len(tasks),
        completed_tasks=sum(t.status == TaskStatus.DONE for t in tasks),
        total_commits=sum(r.gitlab_commits for r in rows),
        total_mrs=sum(r.gitlab_mrs for r in rows),
        members_stats=rows,
    )


def analytics_to_csv(data: AnalyticsOut) -> str:
    buf = io.StringIO()
    # BOM, чтобы Excel корректно открыл кириллицу
    buf.write("﻿")
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([title for _, title in CSV_COLUMNS])
    for row in data.members_stats:
        d = row.model_dump(mode="json")
        writer.writerow([d[key] if d[key] is not None else "" for key, _ in CSV_COLUMNS])
    return buf.getvalue()
