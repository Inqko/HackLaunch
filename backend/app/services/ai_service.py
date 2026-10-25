"""ИИ-координатор (Участник 2): генерация черновиков задач и AI Pulse.

Если GEMINI_API_KEY не задан или запрос упал — используется детерминированный
фоллбэк, чтобы демо работало без сети.
"""

import logging
from collections import Counter

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    HealthStatus,
    Project,
    ProjectMember,
    ProjectRole,
    Specialization,
    Task,
    TaskPriority,
    TaskStatus,
)

logger = logging.getLogger(__name__)

OVERLOAD_OPEN_HOURS = 8.0


# --- Схемы Structured Outputs ---

class AITask(BaseModel):
    title: str
    description: str
    assignee_id: int
    priority: TaskPriority
    estimated_hours: float


class AIPlan(BaseModel):
    tasks: list[AITask]


class AIHealth(BaseModel):
    summary: str
    risks: list[str]
    status: HealthStatus


async def _ask_gemini(prompt: str, schema: type[BaseModel]) -> BaseModel | None:
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        resp = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": schema},
        )
        return resp.parsed
    except Exception:
        logger.exception("Gemini request failed, using fallback")
        return None


# --- Генерация задач ---

FALLBACK_TEMPLATES: dict[Specialization, list[tuple[str, str, TaskPriority, float]]] = {
    Specialization.BACKEND: [
        ("Спроектировать схему БД и модели", "Сущности, связи, миграции", TaskPriority.HIGH, 2.0),
        ("Реализовать REST API основных сущностей", "CRUD + валидация + Swagger", TaskPriority.HIGH, 3.0),
        ("Настроить авторизацию и права доступа", "JWT, проверка ролей", TaskPriority.MEDIUM, 2.0),
    ],
    Specialization.FRONTEND: [
        ("Сверстать основные экраны", "Каркас страниц и навигация", TaskPriority.HIGH, 3.0),
        ("Подключить API к интерфейсу", "Запросы, загрузка, обработка ошибок", TaskPriority.HIGH, 2.5),
        ("Отполировать UI к демо", "Адаптивность, пустые состояния, лоадеры", TaskPriority.MEDIUM, 2.0),
    ],
    Specialization.ML: [
        ("Подобрать модель / API для ключевой ИИ-фичи", "Сравнить 2-3 варианта", TaskPriority.HIGH, 2.0),
        ("Сделать ИИ-сервис с фоллбэком", "Обертка над моделью + мок-ответы", TaskPriority.HIGH, 3.0),
        ("Подготовить демо-данные", "Примеры для показа на защите", TaskPriority.MEDIUM, 1.5),
    ],
    Specialization.DESIGN: [
        ("Собрать вайрфреймы ключевых экранов", "Главный экран, кабинет, аналитика", TaskPriority.HIGH, 2.0),
        ("Сделать UI-кит и стили", "Цвета, типографика, компоненты", TaskPriority.MEDIUM, 2.0),
        ("Оформить питч-презентацию", "Структура + визуал слайдов", TaskPriority.HIGH, 2.0),
    ],
    Specialization.PM: [
        ("Зафиксировать MVP-скоуп", "Что обязательно к защите, что — nice to have", TaskPriority.CRITICAL, 1.0),
        ("Подготовить сценарий демо", "Пошаговый flow показа на 3 минуты", TaskPriority.HIGH, 1.5),
        ("Написать текст питча", "Проблема, решение, демо, команда", TaskPriority.HIGH, 1.5),
    ],
}
FALLBACK_TEMPLATES[Specialization.FULLSTACK] = [
    FALLBACK_TEMPLATES[Specialization.BACKEND][1],
    FALLBACK_TEMPLATES[Specialization.FRONTEND][1],
    ("Настроить деплой / запуск одной командой", "Docker или скрипт запуска", TaskPriority.MEDIUM, 1.5),
]
FALLBACK_TEMPLATES[Specialization.OTHER] = FALLBACK_TEMPLATES[Specialization.PM]


def _fallback_plan(members: list[ProjectMember], extra: str | None) -> list[AITask]:
    tasks = [
        AITask(title=t, description=d, assignee_id=m.user_id, priority=p, estimated_hours=h)
        for m in members
        for t, d, p, h in FALLBACK_TEMPLATES[m.specialization]
    ]
    if extra and members:
        devs = [m for m in members if m.specialization in (Specialization.BACKEND, Specialization.FULLSTACK)]
        owner = (devs or members)[0]
        tasks.insert(0, AITask(
            title=f"Реализовать: {extra[:80]}",
            description=extra,
            assignee_id=owner.user_id,
            priority=TaskPriority.HIGH,
            estimated_hours=3.0,
        ))
    return tasks


def _plan_prompt(project: Project, members: list[ProjectMember], extra: str | None) -> str:
    team = "\n".join(
        f"- assignee_id={m.user_id}, имя: {m.user.name}, специализация: {m.specialization.value}"
        for m in members
    )
    return f"""Ты — ИИ-координатор команды на хакатоне. Декомпозируй проект на конкретные задачи
и распредели их между участниками строго по специализациям. Нагрузка должна быть сбалансирована,
3-5 задач на человека, оценки в часах реалистичны для хакатона (0.5-4 ч).

Проект: {project.name}
Описание: {project.description}
{f"Дополнительный контекст от капитана: {extra}" if extra else ""}

Команда (используй только эти assignee_id):
{team}

Пиши названия и описания задач на русском."""


async def generate_task_drafts(
    db: AsyncSession, project: Project, additional_context: str | None = None
) -> list[Task]:
    members = [m for m in project.members if m.role != ProjectRole.VIEWER]
    plan = await _ask_gemini(_plan_prompt(project, members, additional_context), AIPlan)

    valid_ids = {m.user_id for m in members}
    ai_tasks = [t for t in plan.tasks if t.assignee_id in valid_ids] if plan else []
    if not ai_tasks:
        ai_tasks = _fallback_plan(members, additional_context)

    tasks = [
        Task(
            project_id=project.id,
            title=t.title,
            description=t.description,
            assignee_id=t.assignee_id,
            priority=t.priority,
            estimated_hours=t.estimated_hours,
            status=TaskStatus.AI_DRAFT,
            created_by_ai=True,
        )
        for t in ai_tasks
    ]
    db.add_all(tasks)
    await db.commit()
    for t in tasks:
        await db.refresh(t)
    return tasks


# --- AI Pulse ---

def compute_progress(tasks: list[Task]) -> int:
    """Готовность в % по часам: DONE = 100%, REVIEW = 75%, IN_PROGRESS = 40%."""
    weights = {TaskStatus.DONE: 1.0, TaskStatus.REVIEW: 0.75, TaskStatus.IN_PROGRESS: 0.4}
    total = sum(t.estimated_hours for t in tasks)
    if not total:
        return 0
    done = sum(t.estimated_hours * weights.get(t.status, 0) for t in tasks)
    return round(100 * done / total)


def _heuristic_risks(project: Project, tasks: list[Task]) -> list[str]:
    risks = []
    names = {m.user_id: m.user.name for m in project.members}
    open_tasks = [t for t in tasks if t.status != TaskStatus.DONE]

    if not tasks:
        risks.append("В проекте еще нет утвержденных задач — сгенерируйте план через ИИ")
    unassigned = [t for t in open_tasks if t.assignee_id is None]
    if unassigned:
        risks.append(f"Без исполнителя: {len(unassigned)} задач(и)")
    critical = [t for t in open_tasks if t.priority == TaskPriority.CRITICAL]
    if critical:
        risks.append(f"Не закрыты критичные задачи: {', '.join(t.title for t in critical[:3])}")

    load: Counter[int] = Counter()
    for t in open_tasks:
        if t.assignee_id:
            load[t.assignee_id] += t.estimated_hours
    for uid, hours in load.items():
        if hours > OVERLOAD_OPEN_HOURS:
            risks.append(f"{names.get(uid, uid)} перегружен(а): {hours:g} ч открытых задач")

    in_review = [t for t in tasks if t.status == TaskStatus.REVIEW]
    if len(in_review) >= 3:
        risks.append(f"{len(in_review)} задач(и) ждут ревью — это узкое место")
    return risks


def _status_from_risks(risks: list[str]) -> HealthStatus:
    if not risks:
        return HealthStatus.ON_TRACK
    return HealthStatus.AT_RISK if len(risks) <= 2 else HealthStatus.DELAYED


async def refresh_project_health(db: AsyncSession, project: Project) -> Project:
    tasks = list(await db.scalars(
        select(Task).where(Task.project_id == project.id, Task.status != TaskStatus.AI_DRAFT)
    ))
    score = compute_progress(tasks)
    risks = _heuristic_risks(project, tasks)
    by_status = Counter(t.status.value for t in tasks)

    names = {m.user_id: m.user.name for m in project.members}
    task_lines = "\n".join(
        f"- [{t.status.value}] {t.title} ({t.priority.value}, {t.estimated_hours}ч, "
        f"исполнитель: {names.get(t.assignee_id, 'нет')})"
        for t in tasks
    )
    prompt = f"""Ты — ИИ-трекер прогресса хакатон-проекта. Оцени состояние проекта.
Проект: {project.name}
Описание: {project.description}
Готовность по часам: {score}%
Задачи по статусам: {dict(by_status)}
Задачи:
{task_lines or "нет задач"}
Эвристические риски: {risks}

Дай короткое резюме (2-4 предложения на русском: что готово, кто перегружен, что блокирует релиз),
список конкретных рисков и общий статус."""

    health = await _ask_gemini(prompt, AIHealth)
    if health:
        project.ai_health_summary = health.summary
        project.ai_risks = health.risks
        project.ai_health_status = health.status
    else:
        done = by_status.get(TaskStatus.DONE.value, 0)
        project.ai_health_summary = (
            f"Готовность {score}%. Закрыто {done} из {len(tasks)} задач, "
            f"в работе {by_status.get(TaskStatus.IN_PROGRESS.value, 0)}, "
            f"на ревью {by_status.get(TaskStatus.REVIEW.value, 0)}."
            + (" Критичных рисков не выявлено." if not risks else f" Главный риск: {risks[0]}.")
        )
        project.ai_risks = risks
        project.ai_health_status = _status_from_risks(risks)
    project.ai_progress_score = score
    await db.commit()
    return project
