# Промпты для ИИ-агентов команды

Каждый участник копирует **общий контекст + свой блок** в своего агента (Claude Code / Cursor), открытого в корне репозитория.

---

## Общий контекст (вставлять всем)

```
Мы на хакатоне делаем HackLaunch AI — платформу быстрого запуска хакатон-проектов.
Репозиторий уже содержит рабочий каркас: backend (FastAPI + async SQLAlchemy + SQLite/Postgres)
и frontend (Vite + React + TS + Tailwind). Все экраны и эндпоинты из ТЗ уже работают end-to-end
на моках (GitLab — MockGitLabClient, ИИ — фоллбэк без ключа).

Сначала прочитай README.md (структура, API, распределение зон) и файлы своей зоны.

Правила:
- Контракт API = backend/app/schemas.py, его зеркало = frontend/src/api/types.ts.
  Меняешь контракт — меняй оба файла и предупреди команду.
- Права проверяются через зависимости в backend/app/deps.py (ANY_MEMBER, CAN_EDIT, CAPTAIN_ONLY).
- Задачи AI_DRAFT видит и правит только CAPTAIN; в /tasks и /tasks/my они не попадают.
- VIEWER никогда не получает edit_url материалов.
- Демо должно работать без сети: любые внешние вызовы — с фоллбэком.
- Работай в своей ветке (см. таблицу «Команда» в README), мелкими коммитами, затем PR в main.
  Перед началом: git fetch origin && git switch <своя-ветка> && git merge origin/main.
- Не трогай файлы чужих зон без необходимости.
```

---

## Участник 1 — Backend Core & RBAC (ветка `feature/backend-core`)

```
Твоя зона: backend/app/models.py, deps.py, security.py, routers/auth.py, routers/projects.py, routers/materials.py.

Что доделать:
1. Подключить Alembic (сейчас таблицы создаются через create_all в database.py) и сделать первую миграцию.
2. Добавить Postgres в docker-compose.yml (backend + db), проверить работу с asyncpg.
3. Защита от потери капитана: нельзя понизить/удалить последнего CAPTAIN проекта.
4. PATCH /api/projects/{id} (название/описание, только CAPTAIN) и DELETE проекта.
5. Валидация ссылок материалов (http/https; для GOOGLE_* — домен docs.google.com).
6. Сид-скрипт backend/seed.py: 5 пользователей, проект «AI Med Assistant» с ролями для демо.
7. Проверить Swagger (/docs): у всех ручек понятные summary и примеры.
```

## Участник 2 — AI Engine, Tasks & MCP (ветка `feature/ai-tasks-mcp`)

```
Твоя зона: backend/app/services/ai_service.py, routers/tasks.py, routers/ai.py, backend/mcp_server.py.

Что доделать:
1. Проверить генерацию задач с реальным GEMINI_API_KEY (google-genai, Structured Outputs через
   response_schema). Улучшить промпт: учитывать уже существующие задачи, не дублировать их,
   балансировать часы между участниками.
2. AI Pulse: в refresh_project_health учитывать время с последнего обновления задач,
   добавить рекомендации команде (отдельное поле в AIStatusOut + types.ts).
3. Автообновление AI Pulse после перевода задачи в DONE (фоном, без блокировки ответа).
4. MCP: добавить tool list_projects и get_drafts; описать в README пример диалога с Claude Desktop.
5. Фоллбэк-шаблоны (FALLBACK_TEMPLATES) сделать «умнее»: подставлять ключевые слова из описания проекта.
```

## Участник 3 — GitLab Integration & Analytics (ветка `feature/gitlab-analytics`)

```
Твоя зона: backend/app/services/gitlab_service.py, services/analytics_service.py, routers/analytics.py.

Что доделать:
1. Проверить RealGitLabClient на реальном токене (создание репо, инвайт по gitlab_username,
   сбор коммитов и MR). Учесть, что коммиты сопоставляются по email/имени — добавить в профиль
   пользователя поле gitlab_email при необходимости (согласовать с Участником 1).
2. Кэшировать статистику GitLab на 1-2 минуты, чтобы страница аналитики не тормозила.
3. Эндпоинт POST /api/projects/{id}/gitlab/connect — привязать уже существующий репозиторий по URL.
4. Экспорт в XLSX (openpyxl) в дополнение к CSV/JSON.
5. Добавить в аналитику динамику: задачи, закрытые по часам (для графика на фронте).
```

## Участник 4 — Frontend: Project Board & AI Flow (ветка `feature/frontend-board`)

```
Твоя зона: frontend/src/pages/ProjectBoardPage.tsx, frontend/src/components/project/*.

Что доделать:
1. Канбан: оптимистичное перемещение карточек (без ожидания ответа), модалка редактирования
   задачи по клику на карточку (PATCH /api/tasks/{id}), удаление.
2. CaptainApprovalModal: drag-and-drop задач между участниками, индикатор суммарных часов
   на каждого участника, кнопка «Перегенерировать» с доп. контекстом.
3. AI Pulse: красивая визуализация (кольцевой прогресс, цвет по статусу), анимация «ИИ думает».
4. MaterialsWidget: превью/иконки по типу, подтверждение удаления.
5. Пустые состояния и лоадеры-скелетоны на доске.
```

## Участник 5 — Frontend: Auth, Personal Cabinet & Analytics (ветка `feature/frontend-cabinet`)

```
Твоя зона: frontend/src/pages/{Login,Register,Projects,MyWorkspace,Team,Analytics}Page.tsx,
frontend/src/context/AuthContext.tsx, frontend/src/components/AppLayout.tsx.

Что доделать:
1. Страница профиля: изменение имени и gitlab_username (PATCH /api/users/me).
2. Личный кабинет: таймер работы над задачей (локально, start/stop), группировка по статусам,
   личная статистика за сегодня.
3. Команда: поиск пользователя по email с подсказкой, понятные ошибки (пользователь не зарегистрирован).
4. Аналитика: круговая диаграмма вклада (contribution_percent), выбор метрики для графика.
5. Тосты для успехов/ошибок вместо ErrorText, адаптив под мобильный.
```
