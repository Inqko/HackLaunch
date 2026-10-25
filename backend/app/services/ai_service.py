"""ИИ-координатор (Участник 2): генерация черновиков задач и AI Pulse.

Провайдер — DeepSeek или Gemini (AI_PROVIDER в .env). Если ключа нет или запрос
упал — используется детерминированный фоллбэк, чтобы демо работало без сети.
"""

import asyncio
import json
import logging
from collections import Counter
from dataclasses import dataclass, field

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
    title: str = Field(
        min_length=5,
        description="Конкретное действие с предметом проекта: «Сделать эндпоинт POST /recipes/scan "
        "для распознавания фото рецепта», а не «Настроить API»",
    )
    description: str = Field(
        min_length=60,
        description="3-5 предложений: что именно делаем, зачем это проекту и пользователю, "
        "как связано с другими частями системы",
    )
    technical_details: list[str] = Field(
        default=[],
        description="Конкретика реализации: эндпоинты с методами, таблицы и поля, экраны и компоненты, "
        "библиотеки и модели, форматы данных. Для PM/дизайна — артефакты и инструменты",
    )
    steps: list[str] = Field(
        min_length=2, description="4-8 шагов в порядке выполнения, каждый — конкретное действие"
    )
    acceptance_criteria: list[str] = Field(
        min_length=1, description="3-6 проверяемых критериев: что можно открыть, вызвать или показать"
    )
    deliverable: str = Field(default="", description="Что конкретно покажем на демо после выполнения задачи")
    depends_on: str | None = Field(
        default=None, description="От какой задачи или участника зависит, если зависит"
    )
    assignee_id: int
    priority: TaskPriority
    estimated_hours: float

    def full_description(self) -> str:
        parts = [self.description.strip()]
        if self.technical_details:
            parts.append("Технические детали:\n" + "\n".join(f"- {d}" for d in self.technical_details))
        if self.steps:
            parts.append("Шаги:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(self.steps, 1)))
        if self.acceptance_criteria:
            parts.append("Критерии готовности:\n" + "\n".join(f"- {c}" for c in self.acceptance_criteria))
        if self.deliverable:
            parts.append(f"Результат для демо: {self.deliverable}")
        if self.depends_on:
            parts.append(f"Зависит от: {self.depends_on}")
        return "\n\n".join(parts)


class ProjectAnalysis(BaseModel):
    core_features: list[str] = Field(
        default=[], description="3-6 ключевых фич MVP, которые обязательно покажем на защите"
    )
    architecture: str = Field(
        default="", description="Как устроено решение: фронтенд, бэкенд, ИИ/ML, данные, внешние API — 3-5 предложений"
    )
    shared_contracts: list[str] = Field(
        default=[], description="Общие контракты между участниками: эндпоинты с методами и полями, "
        "форматы данных — чтобы задачи бэкенда, фронтенда и ML стыковались",
    )
    demo_scenario: str = Field(default="", description="Сценарий демо на защите в 3-5 шагах")


class MemberPlan(BaseModel):
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


async def _post_with_retry(client: httpx.AsyncClient, body: dict, retries: int = MAX_RETRIES) -> httpx.Response:
    # Бесплатные аккаунты у провайдеров часто получают 429 при пиковой нагрузке — ждем Retry-After
    for attempt in range(retries + 1):
        resp = await client.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json=body,
        )
        if resp.status_code not in RETRY_STATUSES or attempt == retries:
            resp.raise_for_status()
            return resp
        try:
            delay = min(float(resp.headers.get("retry-after", 5)), MAX_RETRY_DELAY)
        except ValueError:
            delay = 5.0
        logger.warning("LLM %s, retry %d/%d in %.0fs", resp.status_code, attempt + 1, retries, delay)
        await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


async def _ask_deepseek(
    prompt: str, schema: type[BaseModel], temperature: float = 0.3
) -> tuple[BaseModel, str]:
    """OpenAI-совместимый провайдер. При перегрузке/ошибке пробует запасные модели.

    JSON mode без строгой схемы: схема — в системном промпте, ответ валидируем Pydantic,
    при ошибке валидации модель один раз исправляет ответ. Возвращает (ответ, модель).
    """
    models = [settings.deepseek_model, *settings.deepseek_fallback_models]
    # С запасными моделями долго не ждем одну перегруженную — быстрее переключиться
    retries = 1 if len(models) > 1 else MAX_RETRIES
    last_error: Exception | None = None
    async with httpx.AsyncClient(base_url=settings.deepseek_base_url, timeout=110) as client:
        for model in models:
            try:
                return await _ask_model(client, model, prompt, schema, temperature, retries), model
            except (httpx.HTTPError, ValidationError, KeyError, ValueError) as e:
                logger.warning("LLM model %s failed (%s), trying next", model, type(e).__name__)
                last_error = e
    raise last_error or RuntimeError("no models configured")


async def _ask_model(
    client: httpx.AsyncClient, model: str, prompt: str, schema: type[BaseModel], temperature: float, retries: int
) -> BaseModel:
    messages = [
        {
            "role": "system",
            "content": "Отвечай только валидным JSON строго по этой JSON Schema, без пояснений:\n"
            + json.dumps(schema.model_json_schema(), ensure_ascii=False),
        },
        {"role": "user", "content": prompt},
    ]
    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        # С запасом: у reasoning-моделей рассуждения тоже расходуют лимит
        "max_tokens": 8000,
    }
    if settings.deepseek_disable_thinking:
        # Разные chat-шаблоны читают разные ключи, лишние игнорируются
        body["chat_template_kwargs"] = {"thinking": False, "enable_thinking": False}
    for attempt in range(2):
        resp = await _post_with_retry(client, {**body, "messages": messages}, retries)
        content = resp.json()["choices"][0]["message"]["content"] or ""
        try:
            return schema.model_validate_json(_extract_json(content))
        except ValidationError as e:
            if attempt:
                raise
            messages += [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"JSON не прошел валидацию: {e}. Исправь (если поля "
                 "слишком короткие — распиши подробнее) и верни JSON целиком."},
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


async def _ask_llm_meta(
    prompt: str, schema: type[BaseModel], temperature: float = 0.3
) -> tuple[BaseModel | None, str | None]:
    """(ответ, модель) или (None, None), если ИИ недоступен — тогда вызывающий берет фоллбэк."""
    provider = _active_provider()
    if provider is None:
        return None, None
    try:
        if provider == "deepseek":
            return await _ask_deepseek(prompt, schema, temperature)
        return await _ask_gemini(prompt, schema), settings.gemini_model
    except Exception:
        logger.exception("%s request failed, using fallback", provider)
        return None, None


async def _ask_llm(prompt: str, schema: type[BaseModel]) -> BaseModel | None:
    return (await _ask_llm_meta(prompt, schema))[0]


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
        AITask.model_construct(
            title=t, description=d, technical_details=[], steps=[], acceptance_criteria=[], deliverable="",
            depends_on=None, assignee_id=m.user_id, priority=p, estimated_hours=h,
        )
        for t, d, p, h in FALLBACK_TEMPLATES[m.specialization]
    ]


def _fallback_plan(members: list[ProjectMember], extra: str | None) -> list[AITask]:
    tasks = [t for m in members for t in _fallback_tasks_for(m)]
    if extra and members:
        devs = [m for m in members if m.specialization in (Specialization.BACKEND, Specialization.FULLSTACK)]
        owner = (devs or members)[0]
        tasks.insert(0, AITask.model_construct(
            title=f"Реализовать: {extra[:80]}", description=extra, technical_details=[], steps=[],
            acceptance_criteria=[], deliverable="", depends_on=None,
            assignee_id=owner.user_id, priority=TaskPriority.HIGH, estimated_hours=3.0,
        ))
    return tasks


SPEC_FOCUS = {
    Specialization.BACKEND: "API, модели данных, бизнес-логика, интеграции, авторизация",
    Specialization.FRONTEND: "экраны, компоненты, состояния, работа с API, UX ключевого сценария",
    Specialization.ML: "модели и промпты, подготовка данных, качество ответов, ИИ-сервис с фоллбэком",
    Specialization.DESIGN: "пользовательский сценарий, макеты ключевых экранов, UI-кит, визуал презентации",
    Specialization.PM: "скоуп MVP, сценарий демо, питч, тексты, проверка готовности к защите",
    Specialization.FULLSTACK: "сквозные фичи от API до экрана, запуск и деплой",
    Specialization.OTHER: "то, что усиливает защиту: исследование, контент, демо-данные",
}

EXAMPLE = """Плохо (шаблонно): «Настроить API» — «Сделать REST API для проекта».
Хорошо: «Сделать эндпоинт POST /api/prescriptions/scan для распознавания фото рецепта» —
description: «Врач загружает фото рецепта, сервис извлекает препараты и дозировки, чтобы дальше
проверить их совместимость. Это первый шаг основного сценария демо; фронтенд и ML ждут этот контракт.»
technical_details: [«POST /api/prescriptions/scan, multipart: file (jpg/png до 10 МБ)»,
«ответ: {id, drugs: [{name, dose, frequency}], confidence}», «таблица prescriptions: id, user_id,
image_path, raw_text, parsed_json, created_at», «OCR: вызов ML-сервиса /ocr, таймаут 15 с, фоллбэк — мок»]
steps: 4-8 конкретных действий; acceptance_criteria: «фото из папки demo/ возвращает ≥2 препарата»,
«не-изображение → 400 с понятной ошибкой», «эндпоинт виден в Swagger с примером ответа»;
deliverable: «на демо загружаем фото и сразу видим распознанный список препаратов»."""


def _team_lines(members: list[ProjectMember]) -> str:
    return "\n".join(
        f"- {m.user.name} — {m.specialization.value} (зона: {SPEC_FOCUS[m.specialization]})" for m in members
    )


def _project_block(project: Project, extra: str | None) -> str:
    return (
        f"Проект: {project.name}\nОписание идеи: {project.description}\n"
        + (f"Дополнительный контекст от капитана (обязательно учти): {extra}\n" if extra else "")
    )


def _analysis_prompt(project: Project, members: list[ProjectMember], extra: str | None) -> str:
    return f"""Ты — опытный техлид команды на хакатоне. Коротко продумай решение, прежде чем раздавать задачи.

{_project_block(project, extra)}
Команда:
{_team_lines(members)}

Заполни: core_features — 3-6 ключевых фич MVP для защиты; architecture — как устроено решение
(3-5 предложений); shared_contracts — 3-8 общих контрактов между участниками (эндпоинты с методами
и полями, форматы данных); demo_scenario — сценарий демо в 3-5 шагах. Пиши кратко, на русском. Верни JSON."""


def _member_prompt(
    project: Project, members: list[ProjectMember], member: ProjectMember,
    analysis: ProjectAnalysis | None, existing: list[Task], extra: str | None,
) -> str:
    plan = (
        f"""План команды (общий для всех участников, опирайся на него):
Ключевые фичи: {"; ".join(analysis.core_features)}
Архитектура: {analysis.architecture}
Общие контракты: {"; ".join(analysis.shared_contracts)}
Сценарий демо: {analysis.demo_scenario}
"""
        if analysis else ""
    )
    existing_lines = "\n".join(f"- [{t.status.value}] {t.title}" for t in existing) or "нет"
    return f"""Ты — опытный техлид команды на хакатоне. Напиши задачи для ОДНОГО участника так подробно,
чтобы он сразу сел и начал делать, без уточнений.

{_project_block(project, extra)}
{plan}
Команда: 
{_team_lines(members)}

Участник: {member.user.name}, специализация {member.specialization.value}
(зона: {SPEC_FOCUS[member.specialization]}). assignee_id = {member.user_id}.

Требования:
- 3-4 задачи только для этого участника, суммарно 7-10 часов, 1-4 часа на задачу.
- Каждая задача — про ЭТОТ проект: его сущности, экраны, данные. Запрещены общие формулировки,
  которые подошли бы любому проекту («Настроить API», «Сверстать основные экраны», «Подготовить
  презентацию»). Если название можно скопировать в другой проект — перепиши.
- technical_details — конкретика: эндпоинты и методы, поля таблиц, экраны и компоненты, библиотеки,
  форматы данных. Используй общие контракты из плана, чтобы задачи участников стыковались.
- acceptance_criteria — проверяемые: что можно открыть, вызвать или показать.
- Доска задач, трекинг и GitLab-репозиторий уже есть в HackLaunch — не ставь задач на Trello/Notion/Jira,
  распределение задач или создание репозитория.
- Не дублируй существующие задачи:
{existing_lines}

Пример уровня детализации:
{EXAMPLE}

Пиши на русском. Верни JSON."""


@dataclass
class GenerationResult:
    tasks: list[Task]
    used_ai: bool
    model: str | None
    fallback_members: list[str] = field(default_factory=list)


# Провайдер на бесплатном тарифе ограничивает параллельные запросы
MEMBER_CONCURRENCY = 2


async def generate_task_drafts(
    db: AsyncSession, project: Project, additional_context: str | None = None
) -> GenerationResult:
    """Сначала короткий анализ проекта, затем задачи для каждого участника отдельным запросом.

    Маленькие запросы укладываются в таймаут провайдера (~100 с) и не ломают всю генерацию:
    если запрос для участника не удался, только ему достаются шаблонные задачи.
    """
    members = [m for m in project.members if m.role != ProjectRole.VIEWER]
    existing = list(await db.scalars(select(Task).where(Task.project_id == project.id)))
    analysis, model = await _ask_llm_meta(_analysis_prompt(project, members, additional_context), ProjectAnalysis)

    sem = asyncio.Semaphore(MEMBER_CONCURRENCY)

    async def plan_for(m: ProjectMember) -> tuple[ProjectMember, list[AITask], str | None]:
        async with sem:
            plan, used = await _ask_llm_meta(
                _member_prompt(project, members, m, analysis, existing, additional_context),
                MemberPlan, temperature=0.5,
            )
        tasks = [t for t in plan.tasks if t.assignee_id == m.user_id] if plan else []
        if plan and not tasks:  # модель перепутала assignee_id — задачи все равно этого участника
            tasks = plan.tasks
            for t in tasks:
                t.assignee_id = m.user_id
        return m, tasks, used

    ai_tasks: list[AITask] = []
    fallback_members: list[str] = []
    models_used = {model} if model else set()
    for m, tasks, used in await asyncio.gather(*(plan_for(m) for m in members)):
        if tasks:
            ai_tasks += tasks
            models_used.add(used)
        else:
            logger.warning("LLM failed for member %s, using templates", m.user_id)
            fallback_members.append(m.user.name)
            ai_tasks += _fallback_tasks_for(m)
    used_ai = len(fallback_members) < len(members)
    if not used_ai and additional_context and members:
        ai_tasks = _fallback_plan(members, additional_context)

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
    return GenerationResult(
        tasks=tasks, used_ai=used_ai,
        model=", ".join(sorted(m for m in models_used if m)) if used_ai else None,
        fallback_members=fallback_members if used_ai else [],
    )


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
