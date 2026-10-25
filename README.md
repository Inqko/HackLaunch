# HackLaunch AI

Платформа быстрого запуска хакатон-проектов: доски проектов в стиле Miro, ИИ-координатор, который раздает подробные задачи участникам (с утверждением Капитаном), ИИ-ревью кода с Merge Request в GitLab, прикрепление GitLab-репозитория, умные ссылки на Google Docs/Slides по ролям, аналитика с выгрузкой и MCP-сервер.

Все экраны и эндпоинты работают end-to-end; без ключей — на моках (шаблонные задачи, mock GitLab), поэтому демо можно показать без сети. Промпты для ИИ-агентов команды — в [docs/AGENT_PROMPTS.md](docs/AGENT_PROMPTS.md).

## Быстрый старт

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # по умолчанию SQLite + mock GitLab + фоллбэк ИИ
uvicorn app.main:app --reload # http://localhost:8000/docs — Swagger
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173, /api проксируется на :8000
```

Чтобы включить настоящий ИИ и GitLab, заполните `backend/.env` (подробнее — разделы ниже):

```bash
# ИИ: любой OpenAI-совместимый провайдер (у нас — DeepSeek через inference.dahl.global)
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://inference.dahl.global/v1
DEEPSEEK_MODEL=deepseek-ai/DeepSeek-V4-Flash-0731
DEEPSEEK_DISABLE_THINKING=true
DEEPSEEK_FALLBACK_MODELS=["zai-org/GLM-5.3-Flash","MiniMaxAI/MiniMax-M2.7"]

# GitLab (токен со scope api)
USE_MOCK_GITLAB=false
GITLAB_TOKEN=glpat-...
```

Вместо DeepSeek можно указать `GEMINI_API_KEY` (`AI_PROVIDER=auto|deepseek|gemini`).

Пароли проверяются по политике (8+ символов, строчная/заглавная буква, цифра, спецсимвол). Смена и восстановление пароля подтверждаются кодом из письма: настройте `SMTP_*` в `backend/.env`. Без SMTP код пишется в лог бэкенда, а при `EMAIL_DEBUG=true` (по умолчанию) показывается в интерфейсе как демо-код.

**MCP-сервер** (Claude Desktop / Cursor):

```json
{
  "mcpServers": {
    "hacklaunch": {
      "command": "/abs/path/HackLaunch/backend/.venv/bin/python",
      "args": ["/abs/path/HackLaunch/backend/mcp_server.py"],
      "cwd": "/abs/path/HackLaunch/backend"
    }
  }
}
```

Tools: `generate_tasks_from_prompt`, `get_project_health`, `create_single_task`, `assign_task`, `update_task_status`.

## ИИ: генерация задач

Капитан нажимает «Сгенерировать задачи через ИИ» на доске проекта:

1. Короткий анализ проекта: ключевые фичи MVP, архитектура, общие контракты между участниками (эндпоинты, форматы данных), сценарий демо.
2. Для каждого участника — отдельный запрос (по 2 параллельно): 3-4 задачи по его специализации с описанием, техническими деталями, шагами, критериями готовности и результатом для демо. Маленькие запросы укладываются в таймаут провайдера (~100 с).
3. Задачи сохраняются черновиками (`AI_DRAFT`); капитан правит и утверждает их — после этого они появляются на доске и в «Моих задачах».

Если основная модель перегружена (429), пробуются `DEEPSEEK_FALLBACK_MODELS`. Если ИИ не ответил — участнику подставляются шаблонные задачи, а интерфейс показывает предупреждение. На бесплатном тарифе провайдера бывают перегрузки: для надежного демо пополните баланс провайдера.

## ИИ-ревью задач

1. «Взять в работу» — платформа создает в GitLab ветку `task-<id>-<название>`; в «Моих задачах» видна команда `git fetch origin && git switch task-...`.
2. Участник пушит в ветку — задача уходит в «На ревью» («ИИ проверяет…»). Push замечается фоновым опросом веток (раз в `REVIEW_POLL_SECONDS`, по умолчанию 60 с), вебхуком `Push Hook` или кнопкой «На ревью».
3. ИИ сверяет diff с описанием и критериями готовности задачи:
   - есть ошибки — замечания (файл, строка, что исправить), задача обратно «В работе»; следующий push запускает ревью снова;
   - все хорошо — создается Merge Request с отчетом ИИ, задача ждет капитана.
4. Капитан в окне ревью: «Влить MR и закрыть задачу» (merge → «Готово») или «Отклонить» с комментарием (→ «В работе»).

Если ИИ недоступен, MR все равно создается и капитан проверяет код сам. История ревью хранится в `task_reviews` и дублируется комментариями в MR. Ручное перетаскивание задачи по доске выходит из цикла ревью. Для ревью нужен прикрепленный репозиторий, к которому есть доступ у владельца `GITLAB_TOKEN`.

## GitLab: репозиторий, участники и задачи

Капитан создает репозиторий на gitlab.com сам (лучше в группе команды) и прикрепляет его ссылкой: полем при создании проекта или кнопкой «Прикрепить репозиторий» в шапке проекта (`PUT /api/projects/{id}/gitlab/repository`). Подходят ссылки `https://gitlab.com/group/repo`, `...repo.git`, `.../-/tree/main` и `git@gitlab.com:group/repo.git`. Ссылка сохраняется всегда; ID репозитория бэкенд узнает через API, а если GitLab недоступен — позже, при синхронизации. Каждый участник проекта с заполненным `gitlab_username` получает доступ Developer.

Задачи синхронизируются с issues GitLab:
- issue создаётся при утверждении черновика ИИ или создании задачи вручную (статус `TODO`);
- изменения названия/описания/приоритета/исполнителя и перевод в `DONE` обновляют issue (закрывают его);
- удаление задачи закрывает issue и снимает метку `GITLAB_TASK_LABEL`, чтобы импорт её не воскресил;
- обратный импорт подтягивает issues с этой меткой как задачи проекта (`open` → `TODO/IN_PROGRESS/REVIEW`, `closed` → `DONE`), дедупликация по `iid` (`Task.gitlab_issue_iid`).

**Ручная синхронизация:** кнопка «GitLab» на доске или `POST /api/projects/{id}/gitlab/sync` (CAPTAIN/MEMBER). Она же приглашает всех участников с `gitlab_username`.

**Вебхуки (синхронизация на каждый push/issue):**

```bash
# backend/.env
USE_MOCK_GITLAB=false
GITLAB_TOKEN=...                  # scope api
GITLAB_WEBHOOK_URL=https://<public-host>/api/webhooks/gitlab
GITLAB_WEBHOOK_SECRET=<random>
GITLAB_TASK_LABEL=hacklaunch
```

В dev публичный URL удобно получить через `ngrok http 8000` (или cloudflared). Вебхук регистрируется автоматически при прикреплении репозитория, а для уже прикрепленного — после ручной синхронизации. GitLab присылает `X-Gitlab-Token`; без совпадения с секретом эндпоинт отвечает 401.

Без токена (`USE_MOCK_GITLAB=true`, по умолчанию) работает `MockGitLabClient`: репозиторий и issues живут в памяти процесса, поэтому весь сценарий можно показать без сети. Ограничения: `gitlab_username` должен существовать в вашем GitLab, токен должен видеть пользователей, а вебхуки требуют публичный HTTPS-URL.

### Общий конфиг команды

Настройки читаются из `.env.shared`, затем из `.env` — локальный файл перекрывает общий. Это позволяет закоммитить общие параметры команды (`GITLAB_NAMESPACE_ID`, метку) и не дублировать их в каждом окружении.

⚠️ `GITLAB_TOKEN` — секрет. Не коммитьте его в **публичный** репозиторий. Для приватного репозитория допустим короткоживущий общий токен: после хакатона отзовите его и удалите `.env.shared`. Файл добавлен в `.gitignore` и попадает в git только через `git add -f`.

Новые колонки (`tasks.gitlab_issue_iid`, `completed_at`, поля ИИ-ревью, `users.avatar_url`) и таблица `task_reviews` добавляются автоматически при старте (create_all + лёгкая миграция для старых dev-баз).

## Структура

```
backend/
  app/
    main.py                 FastAPI, CORS, подключение роутеров
    config.py               настройки из .env
    database.py             async engine, сессии, create_all на старте
    models.py               SQLAlchemy-модели и enum'ы
    schemas.py              Pydantic-схемы = контракт API
    security.py             bcrypt + JWT
    deps.py                 get_current_user, require_project_role (RBAC)
    routers/                auth, users (аватары), projects (+members), tasks, review, ai,
                            materials, analytics, gitlab (репозиторий, синхронизация, вебхук)
    services/
      gitlab_service.py     Real/Mock GitLab клиент, мост задачи <-> issues
      ai_service.py         генерация задач (DeepSeek/Gemini + запасные модели + фоллбэк), AI Pulse
      review_service.py     ИИ-ревью: ветки задач, diff, MR, merge, опрос веток
      analytics_service.py  сбор статистики + CSV
  mcp_server.py             MCP-сервер (FastMCP)
frontend/src/
  api/                      types.ts (зеркало schemas.py), client.ts, endpoints.ts
  context/                  AuthContext, ProjectContext
  components/ui/            примитивы в стиле shadcn/ui
  components/project/       AIPulseWidget, KanbanBoard, CaptainApprovalModal, ReviewModal,
                            AttachRepoModal, MaterialsWidget
  pages/                    Login, Register, Projects, ProjectBoard, MyWorkspace, Cabinet, Team, Analytics
```

## API

| Метод | Путь | Кто |
| :-- | :-- | :-- |
| POST | `/api/auth/register`, `/api/auth/login` | все |
| GET/PATCH | `/api/users/me` | авторизованный |
| POST/DELETE | `/api/users/me/avatar` | авторизованный |
| POST | `/api/users/me/password/request-code` | авторизованный |
| POST | `/api/users/me/password` | авторизованный (нужен код из письма) |
| POST | `/api/auth/password-reset/request`, `/confirm` | все |
| GET/POST | `/api/projects` | авторизованный (создатель → CAPTAIN) |
| GET | `/api/projects/{id}` | участник проекта (+ `my_role`) |
| DELETE | `/api/projects/{id}` | CAPTAIN (задачи и материалы удаляются, GitLab-репозиторий остаётся) |
| POST | `/api/projects/{id}/members` | CAPTAIN |
| PATCH/DELETE | `/api/projects/{id}/members/{user_id}` | CAPTAIN |
| GET | `/api/projects/{id}/tasks` | участник (без `AI_DRAFT`) |
| POST | `/api/projects/{id}/tasks` | CAPTAIN; MEMBER — только на себя |
| GET | `/api/projects/{id}/tasks/my` | участник |
| GET | `/api/projects/{id}/tasks/drafts` | CAPTAIN |
| POST | `/api/projects/{id}/tasks/approve-batch` | CAPTAIN (`id: null` = своя задача) |
| PATCH | `/api/tasks/{task_id}` | CAPTAIN; MEMBER — только свои задачи и без смены исполнителя (черновики — только CAPTAIN) |
| DELETE | `/api/tasks/{task_id}` | CAPTAIN |
| POST | `/api/projects/{id}/ai/generate-tasks` | CAPTAIN (ответ: `tasks`, `used_ai`, `model`, `warning`) |
| POST | `/api/projects/{id}/ai/refresh-status` | CAPTAIN, MEMBER |
| GET | `/api/projects/{id}/materials` | участник (`target_url` по роли, VIEWER не видит `edit_url`) |
| POST | `/api/projects/{id}/materials` | CAPTAIN, MEMBER |
| DELETE | `/api/projects/{id}/materials/{mid}` | CAPTAIN; MEMBER — только добавленные им |
| GET | `/api/projects/{id}/analytics` | CAPTAIN — вся команда; MEMBER — только своя строка (`scope: PERSONAL`) |
| GET | `/api/projects/{id}/analytics/export?format=csv\|json` | CAPTAIN |
| PUT/DELETE | `/api/projects/{id}/gitlab/repository` | CAPTAIN (прикрепить/открепить репозиторий по ссылке) |
| POST | `/api/projects/{id}/gitlab/sync` | CAPTAIN |
| POST | `/api/webhooks/gitlab` | GitLab (`X-Gitlab-Token`) |
| POST | `/api/tasks/{task_id}/review/submit` | исполнитель задачи или CAPTAIN |
| GET | `/api/tasks/{task_id}/reviews` | участник (история ревью + ссылка на MR) |
| POST | `/api/tasks/{task_id}/review/approve`, `/review/reject` | CAPTAIN |

> Где исходные промпты расходились с ТЗ, взят вариант из ТЗ: поле материалов `target_url` (не `access_url`), типы `GOOGLE_SLIDES/GOOGLE_DOCS/FIGMA/OTHER`, личные задачи по `/api/projects/{id}/tasks/my`, пересчет здоровья — `POST /ai/refresh-status`.

## Команда

| # | Зона | Ветка | Основные файлы |
| :-- | :-- | :-- | :-- |
| 1 | Backend Core & RBAC | `feature/backend-core` | `models.py`, `deps.py`, `routers/auth.py`, `routers/projects.py`, `routers/materials.py` |
| 2 | AI Engine, Tasks & MCP | `feature/ai-tasks-mcp` | `routers/tasks.py`, `routers/ai.py`, `services/ai_service.py`, `mcp_server.py` |
| 3 | GitLab & Analytics | `feature/gitlab-analytics` | `services/gitlab_service.py`, `services/analytics_service.py`, `routers/analytics.py` |
| 4 | Frontend: Board & AI Flow | `feature/frontend-board` | `pages/ProjectBoardPage.tsx`, `components/project/*` |
| 5 | Frontend: Auth, Cabinet, Analytics | `feature/frontend-cabinet` | `pages/Login/Register/Projects/MyWorkspace/Team/AnalyticsPage.tsx`, `context/AuthContext.tsx` |

### Git-флоу

```bash
git fetch origin
git switch feature/<своя-ветка>        # ветка уже создана от main
# ...работа, мелкие коммиты...
git push
# PR feature/<ветка> → main; на каждый PR GitHub Action оставляет ИИ-отчет о прогрессе
```

Чтобы подтянуть чужие влитые изменения: `git fetch origin && git merge origin/main` в своей ветке. Перед мержем PR — проверить, что `npm run build` и бэкенд запускаются.
