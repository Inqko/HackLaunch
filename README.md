# HackLaunch AI

Платформа быстрого запуска хакатон-проектов: доски проектов в стиле Miro, ИИ-координатор, который раздает задачи участникам (с утверждением Капитаном), авто-создание GitLab-репозитория, умные ссылки на Google Docs/Slides по ролям, аналитика с выгрузкой и MCP-сервер.

Это **каркас**: все экраны и эндпоинты из ТЗ уже работают end-to-end (без ключей — на моках). Дальше каждый участник развивает свой модуль, см. [docs/AGENT_PROMPTS.md](docs/AGENT_PROMPTS.md).

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

Чтобы включить настоящий ИИ, пропишите `GEMINI_API_KEY` в `backend/.env`. Для настоящего GitLab: `GITLAB_TOKEN`, `USE_MOCK_GITLAB=false` и при желании `GITLAB_NAMESPACE_ID` (группа хакатона).

**MCP-сервер** (Claude Desktop / Cursor):

```json
{
  "mcpServers": {
    "hacklaunch": {
      "command": "/abs/path/xoxoton/backend/.venv/bin/python",
      "args": ["/abs/path/xoxoton/backend/mcp_server.py"],
      "cwd": "/abs/path/xoxoton/backend"
    }
  }
}
```

Tools: `generate_tasks_from_prompt`, `get_project_health`, `create_single_task`, `assign_task`, `update_task_status`.

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
    routers/                auth, projects (+members), tasks, ai, materials, analytics
    services/
      gitlab_service.py     Real/Mock GitLab клиент
      ai_service.py         Gemini (Structured Outputs) + фоллбэк, AI Pulse
      analytics_service.py  сбор статистики + CSV
  mcp_server.py             MCP-сервер (FastMCP)
frontend/src/
  api/                      types.ts (зеркало schemas.py), client.ts, endpoints.ts
  context/                  AuthContext, ProjectContext
  components/ui/            примитивы в стиле shadcn/ui
  components/project/       AIPulseWidget, KanbanBoard, CaptainApprovalModal, MaterialsWidget
  pages/                    Login, Register, Projects, ProjectBoard, MyWorkspace, Team, Analytics
```

## API

| Метод | Путь | Кто |
| :-- | :-- | :-- |
| POST | `/api/auth/register`, `/api/auth/login` | все |
| GET/PATCH | `/api/users/me` | авторизованный |
| POST | `/api/users/me/password` | авторизованный |
| GET/POST | `/api/projects` | авторизованный (создатель → CAPTAIN) |
| GET | `/api/projects/{id}` | участник проекта (+ `my_role`) |
| POST | `/api/projects/{id}/members` | CAPTAIN |
| PATCH/DELETE | `/api/projects/{id}/members/{user_id}` | CAPTAIN |
| GET | `/api/projects/{id}/tasks` | участник (без `AI_DRAFT`) |
| POST | `/api/projects/{id}/tasks` | CAPTAIN, MEMBER |
| GET | `/api/projects/{id}/tasks/my` | участник |
| GET | `/api/projects/{id}/tasks/drafts` | CAPTAIN |
| POST | `/api/projects/{id}/tasks/approve-batch` | CAPTAIN (`id: null` = своя задача) |
| PATCH/DELETE | `/api/tasks/{task_id}` | CAPTAIN, MEMBER (черновики — только CAPTAIN) |
| POST | `/api/projects/{id}/ai/generate-tasks` | CAPTAIN |
| POST | `/api/projects/{id}/ai/refresh-status` | CAPTAIN, MEMBER |
| GET | `/api/projects/{id}/materials` | участник (`target_url` по роли, VIEWER не видит `edit_url`) |
| POST/DELETE | `/api/projects/{id}/materials[/{mid}]` | CAPTAIN, MEMBER |
| GET | `/api/projects/{id}/analytics` | участник |
| GET | `/api/projects/{id}/analytics/export?format=csv\|json` | участник |

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
