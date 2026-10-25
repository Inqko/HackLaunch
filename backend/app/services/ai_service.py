"""ИИ-координатор (Участник 2): генерация черновиков задач и AI Pulse.

Провайдер — DeepSeek или Gemini (AI_PROVIDER в .env). Если ключа нет или запрос
упал — используется детерминированный фоллбэк, чтобы демо работало без сети.
"""

import asyncio
import json
import logging
from collections import Counter

import httpx
from pydantic import BaseModel, Field, ValidationError
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
    title: str = Field(description="Короткое действие: «Сделать…», «Настроить…»")
    description: str = Field(description="2-3 предложения: что делаем, зачем и как это связано с проектом")
    steps: list[str] = Field(
        default=[],
        description="3-6 конкретных шагов: какие технологии, эндпоинты, экраны, файлы, данные",
    )
    acceptance_criteria: list[str] = Field(
        default=[], description="2-4 проверяемых критерия готовности"
    )
    depends_on: str | None = Field(
        default=None, description="От какой задачи или участника зависит, если зависит"
    )
    assignee_id: int
    priority: TaskPriority
    estimated_hours: float

    def full_description(self) -> str:
        parts = [self.description.strip()]
        if self.steps:
            parts.append("Шаги:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(self.steps, 1)))
        if self.acceptance_criteria:
            parts.append("Критерии готовности:\n" + "\n".join(f"- {c}" for c in self.acceptance_criteria))
        if self.depends_on:
            parts.append(f"Зависит от: {self.depends_on}")
        return "\n\n".join(parts)


class AIPlan(BaseModel):
    tasks: list[AITask]


class AIHealth(BaseModel):
    summary: str
    risks: list[str]
    status: HealthStatus


def _active_provider() -> str | None:
    provider = settings.ai_provider.lower()
    if provider == "auto":
        if settings.deepseek_api_key:
            return "deepseek"
        return "gemini" if settings.gemini_api_key else None
    keys = {"deepseek": settings.deepseek_api_key, "gemini": settings.gemini_api_key}
    return provider if keys.get(provider) else None


def _extract_json(content: str) -> str:
    # Провайдеры с JSON mode не всегда строги: бывают ```json-обертки и мусор после объекта
    start = content.find("{")
    if start == -1:
        return content
    try:
        _, end = json.JSONDecoder().raw_decode(content, start)
    except json.JSONDecodeError:
        return content[start:]
    return content[start:end]


RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
MAX_RETRY_DELAY = 20.0


async def _post_with_retry(client: httpx.AsyncClient, body: dict) -> httpx.Response:
    # Бесплатные аккаунты у провайдеров часто получают 429 при пиковой нагрузке — ждем Retry-After
    for attempt in range(MAX_RETRIES + 1):
        resp = await client.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json=body,
        )
        if resp.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
            resp.raise_for_status()
            return resp
        try:
            delay = min(float(resp.headers.get("retry-after", 5)), MAX_RETRY_DELAY)
        except ValueError:
            delay = 5.0
        logger.warning("LLM %s, retry %d/%d in %.0fs", resp.status_code, attempt + 1, MAX_RETRIES, delay)
        await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


async def _ask_deepseek(prompt: str, schema: type[BaseModel]) -> BaseModel:
    # DeepSeek поддерживает только JSON mode без строгой схемы:
    # передаем JSON Schema в промпте и валидируем ответ Pydantic, при ошибке — одна повторная попытка
    messages = [
        {
            "role": "system",
            "content": "Отвечай только валидным JSON строго по этой JSON Schema, без пояснений:\n"
            + json.dumps(schema.model_json_schema(), ensure_ascii=False),
        },
        {"role": "user", "content": prompt},
    ]
    body = {
        "model": settings.deepseek_model,
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
        # С запасом: у reasoning-моделей рассуждения тоже расходуют лимит
        "max_tokens": 16000,
    }
    if settings.deepseek_disable_thinking:
        # Разные chat-шаблоны читают разные ключи, лишние игнорируются
        body["chat_template_kwargs"] = {"thinking": False, "enable_thinking": False}
    async with httpx.AsyncClient(base_url=settings.deepseek_base_url, timeout=180) as client:
        for attempt in range(2):
            resp = await _post_with_retry(client, {**body, "messages": messages})
            content = resp.json()["choices"][0]["message"]["content"] or ""
            try:
                return schema.model_validate_json(_extract_json(content))
            except ValidationError as e:
                if attempt:
                    raise
                messages += [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": f"JSON не прошел валидацию: {e}. Исправь и верни JSON целиком."},
                ]
    raise RuntimeError("unreachable")


async def _ask_gemini(prompt: str, schema: type[BaseModel]) -> BaseModel | None:
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    resp = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": schema},
    )
    return resp.parsed


async def _ask_llm(prompt: str, schema: type[BaseModel]) -> BaseModel | None:
    provider = _active_provider()
    if provider is None:
        return None
    try:
        if provider == "deepseek":
            return await _ask_deepseek(prompt, schema)
        return await _ask_gemini(prompt, schema)
    except Exception:
        logger.exception("%s request failed, using fallback", provider)
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


def _fallback_tasks_for(m: ProjectMember) -> list[AITask]:
    return [
        AITask(title=t, description=d, assignee_id=m.user_id, priority=p, estimated_hours=h)
        for t, d, p, h in FALLBACK_TEMPLATES[m.specialization]
    ]


def _fallback_plan(members: list[ProjectMember], extra: str | None) -> list[AITask]:
    tasks = [t for m in members for t in _fallback_tasks_for(m)]
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


def _plan_prompt(
    project: Project, members: list[ProjectMember], existing: list[Task], extra: str | None
) -> str:
    team = "\n".join(
        f"- assignee_id={m.user_id}, имя: {m.user.name}, специализация: {m.specialization.value}"
        for m in members
    )
    existing_lines = "\n".join(f"- [{t.status.value}] {t.title}" for t in existing) or "нет"
    return f"""Ты — ИИ-координатор команды на хакатоне. Декомпозируй проект на конкретные,
проверяемые задачи и распредели их между участниками строго по специализациям.

Правила:
- Каждый участник из списка команды получает 3-5 задач, никого не пропускай.
- Суммарные часы у участников должны отличаться не больше чем на 30%.
- Оценки реалистичны для хакатона: 0.5-4 часа на задачу.
- Не дублируй уже существующие задачи (список ниже), дополняй их.
- PM / OTHER получают задачи по скоупу, демо, питчу и координации; DESIGN — по UI и презентации.
- Команда уже работает в HackLaunch: доска задач, распределение, трекинг прогресса и GitLab-репозиторий
  есть автоматически — не создавай задач на Trello/Notion/Jira, распределение задач или создание репозитория.
- Название — короткое действие («Сделать…», «Настроить…»).
- Расписывай задачу так, чтобы участник мог начать работу без уточнений:
  description — что делаем и зачем (2-3 предложения, с привязкой к идее проекта);
  steps — 3-6 конкретных шагов (технологии, эндпоинты, экраны, данные — по специализации);
  acceptance_criteria — 2-4 проверяемых критерия, по которым капитан поймет, что задача готова;
  depends_on — если задача ждет результата другой задачи или участника.
- assignee_id — только из списка команды.

Проект: {project.name}
Описание: {project.description}
{f"Дополнительный контекст от капитана (обязательно учти): {extra}" if extra else ""}

Команда:
{team}

Уже существующие задачи:
{existing_lines}

Пиши названия и описания задач на русском. Верни JSON."""


async def generate_task_drafts(
    db: AsyncSession, project: Project, additional_context: str | None = None
) -> list[Task]:
    members = [m for m in project.members if m.role != ProjectRole.VIEWER]
    existing = list(await db.scalars(select(Task).where(Task.project_id == project.id)))
    plan = await _ask_llm(_plan_prompt(project, members, existing, additional_context), AIPlan)

    valid_ids = {m.user_id for m in members}
    ai_tasks = [t for t in plan.tasks if t.assignee_id in valid_ids] if plan else []
    if not ai_tasks:
        ai_tasks = _fallback_plan(members, additional_context)
    else:
        # ИИ иногда «забывает» участника — добираем ему задачи из шаблонов
        covered = {t.assignee_id for t in ai_tasks}
        for m in members:
            if m.user_id not in covered:
                logger.warning("LLM skipped member %s, adding fallback tasks", m.user_id)
                ai_tasks += _fallback_tasks_for(m)

    tasks = [
        Task(
            project_id=project.id,
            title=t.title,
            description=t.full_description(),
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
список конкретных рисков и общий статус. Верни JSON."""

    health = await _ask_llm(prompt, AIHealth)
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
