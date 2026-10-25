"""Интеграция с GitLab REST API v4 (Участник 3).

Без токена или с USE_MOCK_GITLAB=true используется MockGitLabClient,
чтобы демо работало без сети.

Здесь же — двусторонний мост задач и issues:
- задача сайта -> issue (создание, обновление, закрытие, архивирование);
- issues GitLab -> задачи проекта (ручная синхронизация и вебхук).
"""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import (
    Project,
    ProjectMember,
    ProjectRole,
    Task,
    TaskPriority,
    TaskStatus,
    User,
)

logger = logging.getLogger(__name__)

DEVELOPER_ACCESS_LEVEL = 30
CONNECT_RETRIES = 3


def normalize_gitlab_username(value: str | None) -> str | None:
    """GitLab username без @ и пробелов; пустое значение -> None.

    Пользователи часто вводят @username, как в Telegram, но GitLab API
    ожидает чистый логин.
    """
    if not value:
        return None
    username = value.strip().lstrip("@").strip()
    return username or None


@dataclass
class RepoInfo:
    id: int
    web_url: str


@dataclass
class IssueInfo:
    iid: int
    web_url: str = ""
    state: str = "opened"
    title: str = ""
    description: str = ""
    labels: list[str] = field(default_factory=list)
    assignee_usernames: list[str] = field(default_factory=list)


@dataclass
class ContributorStats:
    commits: int = 0
    mrs: int = 0
    last_activity: str | None = None


class GitLabClient(Protocol):
    async def create_repository(self, path: str, name: str, description: str) -> RepoInfo: ...

    async def get_repository(self, path_with_namespace: str) -> RepoInfo: ...

    async def add_member(self, gitlab_project_id: int, username: str) -> None: ...

    async def get_contributor_stats(
        self, gitlab_project_id: int, users: list[User]
    ) -> dict[int, ContributorStats]: ...

    async def create_issue(
        self,
        gitlab_project_id: int,
        title: str,
        description: str,
        assignee_usernames: list[str] | None,
        labels: list[str],
    ) -> IssueInfo: ...

    async def update_issue(
        self,
        gitlab_project_id: int,
        iid: int,
        *,
        title: str | None = None,
        description: str | None = None,
        state_event: str | None = None,
        assignee_usernames: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> IssueInfo | None: ...

    async def list_issues(
        self, gitlab_project_id: int, label: str, state: str = "all"
    ) -> list[IssueInfo]: ...

    async def ensure_webhook(self, gitlab_project_id: int, url: str, token: str) -> None: ...


def repo_path(project: Project) -> str:
    # GitLab path допускает только латиницу; кириллица отбрасывается, id гарантирует уникальность
    slug = re.sub(r"[^a-z0-9]+", "-", project.name.lower()).strip("-") or "project"
    return f"{slug}-{project.id}"


def _issue_from_api(data: dict) -> IssueInfo:
    return IssueInfo(
        iid=int(data["iid"]),
        web_url=data.get("web_url") or "",
        state=data.get("state") or "opened",
        title=data.get("title") or "",
        description=data.get("description") or "",
        labels=list(data.get("labels") or []),
        assignee_usernames=[
            assignee["username"]
            for assignee in (data.get("assignees") or [])
            if assignee.get("username")
        ],
    )


class RealGitLabClient:
    def __init__(self) -> None:
        self._base = f"{settings.gitlab_url.rstrip('/')}/api/v4"
        self._headers = {"PRIVATE-TOKEN": settings.gitlab_token}

    def _client(self) -> httpx.AsyncClient:
        # retries повторяет только неудавшееся соединение (запрос еще не ушел), поэтому
        # безопасно и для POST; спасает от обрывов TLS через VPN/прокси
        return httpx.AsyncClient(
            base_url=self._base,
            headers=self._headers,
            timeout=15,
            transport=httpx.AsyncHTTPTransport(retries=CONNECT_RETRIES),
        )

    async def create_repository(self, path: str, name: str, description: str) -> RepoInfo:
        body = {
            "name": name,
            "path": path,
            "description": (description or "")[:2000],
            "initialize_with_readme": True,
            "visibility": "private",
        }
        if settings.gitlab_namespace_id:
            body["namespace_id"] = settings.gitlab_namespace_id
        async with self._client() as client:
            resp = await client.post("/projects", json=body)
            resp.raise_for_status()
            data = resp.json()
        return RepoInfo(id=data["id"], web_url=data["web_url"])

    async def get_repository(self, path_with_namespace: str) -> RepoInfo:
        async with self._client() as client:
            resp = await client.get(f"/projects/{quote(path_with_namespace, safe='')}")
            resp.raise_for_status()
            data = resp.json()
        return RepoInfo(id=data["id"], web_url=data["web_url"])

    async def add_member(self, gitlab_project_id: int, username: str) -> None:
        username = normalize_gitlab_username(username)
        if not username:
            return
        async with self._client() as client:
            resp = await client.get("/users", params={"username": username})
            resp.raise_for_status()
            found = resp.json()
            if not found:
                logger.warning("GitLab user %s not found", username)
                return

            user_id = found[0]["id"]
            # /members/all учитывает и прямых, и наследуемых участников (например,
            # Owner группы). Повторно приглашать их нельзя: GitLab отвечает 400
            # на попытку понизить унаследованную роль до Developer.
            resp = await client.get(
                f"/projects/{gitlab_project_id}/members/all/{user_id}"
            )
            if resp.status_code == 200:
                logger.info(
                    "GitLab user %s already has access to project %s",
                    username,
                    gitlab_project_id,
                )
                return
            if resp.status_code != 404:
                resp.raise_for_status()

            resp = await client.post(
                f"/projects/{gitlab_project_id}/members",
                json={"user_id": user_id, "access_level": DEVELOPER_ACCESS_LEVEL},
            )
            if resp.status_code == 409:  # 409 — уже участник
                return
            if resp.status_code == 400 and "inherited membership" in resp.text.lower():
                # Гонка: доступ появился между проверкой и приглашением
                return
            resp.raise_for_status()

    async def _resolve_user_id(
        self, client: httpx.AsyncClient, username: str
    ) -> int | None:
        resp = await client.get("/users", params={"username": username})
        resp.raise_for_status()
        found = resp.json()
        return found[0]["id"] if found else None

    async def _resolve_user_ids(
        self, client: httpx.AsyncClient, usernames: list[str]
    ) -> list[int]:
        ids: list[int] = []
        for username in usernames:
            user_id = await self._resolve_user_id(client, username)
            if user_id is not None:
                ids.append(user_id)
        return ids

    async def create_issue(
        self,
        gitlab_project_id: int,
        title: str,
        description: str,
        assignee_usernames: list[str] | None,
        labels: list[str],
    ) -> IssueInfo:
        async with self._client() as client:
            body: dict = {
                "title": title,
                "description": description or "",
                "labels": ",".join(labels),
            }
            assignee_ids = await self._resolve_user_ids(client, assignee_usernames or [])
            if assignee_ids:
                body["assignee_ids"] = assignee_ids
            url = f"/projects/{gitlab_project_id}/issues"
            resp = await client.post(url, json=body)
            if resp.status_code == 400 and "assignee_ids" in body:
                # Участник есть в GitLab, но не в проекте — issue все равно создаем,
                # просто без назначения (иначе одна ошибка блокирует всю задачу).
                logger.warning(
                    "GitLab rejected assignees for project %s, retrying without them",
                    gitlab_project_id,
                )
                body.pop("assignee_ids")
                resp = await client.post(url, json=body)
            resp.raise_for_status()
            return _issue_from_api(resp.json())

    async def update_issue(
        self,
        gitlab_project_id: int,
        iid: int,
        *,
        title: str | None = None,
        description: str | None = None,
        state_event: str | None = None,
        assignee_usernames: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> IssueInfo | None:
        async with self._client() as client:
            body: dict = {}
            if title is not None:
                body["title"] = title
            if description is not None:
                body["description"] = description
            if labels is not None:
                body["labels"] = ",".join(labels)
            if state_event:
                body["state_event"] = state_event
            if assignee_usernames is not None:
                assignee_ids = await self._resolve_user_ids(client, assignee_usernames)
                # Пустой список — осознанно снимаем назначение.
                # Если username не найден, лучше не трогать назначение в GitLab.
                if assignee_ids or not assignee_usernames:
                    body["assignee_ids"] = assignee_ids
            if not body:
                return None
            url = f"/projects/{gitlab_project_id}/issues/{iid}"
            resp = await client.put(url, json=body)
            if resp.status_code == 400 and "assignee_ids" in body:
                logger.warning(
                    "GitLab rejected assignees for issue %s, retrying without them", iid
                )
                body.pop("assignee_ids")
                resp = await client.put(url, json=body)
            resp.raise_for_status()
            return _issue_from_api(resp.json())

    async def list_issues(
        self, gitlab_project_id: int, label: str, state: str = "all"
    ) -> list[IssueInfo]:
        params = {"labels": label, "state": state}
        async with self._client() as client:
            items = await self._paginate(
                client, f"/projects/{gitlab_project_id}/issues", params
            )
        return [_issue_from_api(item) for item in items]

    async def ensure_webhook(
        self, gitlab_project_id: int, url: str, token: str
    ) -> None:
        async with self._client() as client:
            resp = await client.get(f"/projects/{gitlab_project_id}/hooks")
            resp.raise_for_status()
            if any(hook.get("url") == url for hook in resp.json()):
                return
            resp = await client.post(
                f"/projects/{gitlab_project_id}/hooks",
                json={
                    "url": url,
                    "token": token,
                    "push_events": True,
                    "issues_events": True,
                    "merge_requests_events": False,
                    "note_events": False,
                    "enable_ssl_verification": True,
                },
            )
            resp.raise_for_status()

    async def _paginate(self, client: httpx.AsyncClient, url: str, params: dict) -> list[dict]:
        items: list[dict] = []
        for page in range(1, 11):
            resp = await client.get(url, params={**params, "per_page": 100, "page": page})
            resp.raise_for_status()
            batch = resp.json()
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    async def get_contributor_stats(
        self, gitlab_project_id: int, users: list[User]
    ) -> dict[int, ContributorStats]:
        stats = {u.id: ContributorStats() for u in users}
        async with self._client() as client:
            commits = await self._paginate(
                client, f"/projects/{gitlab_project_id}/repository/commits", {"all": True}
            )
            mrs = await self._paginate(
                client, f"/projects/{gitlab_project_id}/merge_requests", {"state": "all"}
            )
            accounts = {}
            for u in users:
                username = normalize_gitlab_username(u.gitlab_username)
                if not username:
                    continue
                accounts[u.id] = {"username": username}
                try:
                    resp = await client.get("/users", params={"username": username})
                    resp.raise_for_status()
                    if found := resp.json():
                        accounts[u.id] = found[0]
                except httpx.HTTPError:
                    logger.warning("GitLab user %s lookup failed", username)

        # Коммиты в API не содержат username, поэтому сопоставляем по email, а если
        # не вышло — по имени автора. Пустые ключи не участвуют в сравнении: раньше
        # коммит без email засчитывался первому участнику без gitlab_username
        by_email: dict[str, int] = {}
        by_name: dict[str, set[int]] = {}
        for u in users:
            account = accounts.get(u.id, {})
            for email in (u.email, account.get("public_email"), account.get("commit_email")):
                if email:
                    by_email.setdefault(email.strip().lower(), u.id)
            for name in (u.name, account.get("name"), account.get("username")):
                if name and name.strip():
                    by_name.setdefault(name.strip().lower(), set()).add(u.id)

        for c in commits:
            # Merge-коммиты создаёт кнопка Merge — это не работа автора, MR учитываем отдельно
            if len(c.get("parent_ids") or []) > 1:
                continue
            user_id = by_email.get((c.get("author_email") or "").strip().lower())
            if user_id is None:
                candidates = by_name.get((c.get("author_name") or "").strip().lower(), set())
                # Одинаковые имена у двух участников — не угадываем
                user_id = next(iter(candidates)) if len(candidates) == 1 else None
            if user_id is not None:
                s = stats[user_id]
                s.commits += 1
                s.last_activity = _latest(s.last_activity, c.get("committed_date"))

        by_gitlab_id = {a["id"]: uid for uid, a in accounts.items() if a.get("id") is not None}
        by_username = {a["username"].lower(): uid for uid, a in accounts.items() if a.get("username")}
        for mr in mrs:
            # Закрытые без слияния MR не вклад; открытые и влитые — вклад
            if mr.get("state") == "closed":
                continue
            author = mr.get("author") or {}
            user_id = by_gitlab_id.get(author.get("id")) or by_username.get(
                (author.get("username") or "").lower()
            )
            if user_id is not None:
                s = stats[user_id]
                s.mrs += 1
                s.last_activity = _latest(s.last_activity, mr.get("merged_at") or mr.get("created_at"))
        return stats


def _latest(current: str | None, candidate: str | None) -> str | None:
    """Самая поздняя из двух дат GitLab в UTC ISO.

    Строки сравнивать нельзя: GitLab отдаёт даты коммитов с часовым поясом
    автора (+03:00), а MR — в UTC (Z), и «позже» по строке не значит позже.
    """
    if not candidate:
        return current
    try:
        moment = datetime.fromisoformat(candidate.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return current
    if current and datetime.fromisoformat(current) >= moment:
        return current
    return moment.isoformat()


# In-memory состояние mock-клиента: живёт в рамках процесса, чтобы демо работало
# без GitLab (создали задачу -> увидели issue -> синхронизировали обратно).
_MOCK_ISSUES: dict[int, dict[int, IssueInfo]] = {}
_MOCK_ISSUE_SEQ = 0


def _mock_next_iid() -> int:
    global _MOCK_ISSUE_SEQ
    _MOCK_ISSUE_SEQ += 1
    return _MOCK_ISSUE_SEQ


class MockGitLabClient:
    async def create_repository(self, path: str, name: str, description: str) -> RepoInfo:
        digest = int(hashlib.md5(path.encode()).hexdigest()[:6], 16)
        return RepoInfo(
            id=100000 + digest % 900000,
            web_url=f"{settings.gitlab_url.rstrip('/')}/hacklaunch-demo/{path}",
        )

    async def get_repository(self, path_with_namespace: str) -> RepoInfo:
        digest = int(hashlib.md5(path_with_namespace.encode()).hexdigest()[:6], 16)
        return RepoInfo(
            id=100000 + digest % 900000,
            web_url=f"{settings.gitlab_url.rstrip('/')}/{path_with_namespace}",
        )

    async def add_member(self, gitlab_project_id: int, username: str) -> None:
        logger.info("[mock] add %s to GitLab project %s", username, gitlab_project_id)

    async def create_issue(
        self,
        gitlab_project_id: int,
        title: str,
        description: str,
        assignee_usernames: list[str] | None,
        labels: list[str],
    ) -> IssueInfo:
        iid = _mock_next_iid()
        issue = IssueInfo(
            iid=iid,
            web_url=(
                f"{settings.gitlab_url.rstrip('/')}/hacklaunch-demo/"
                f"{gitlab_project_id}/-/issues/{iid}"
            ),
            state="opened",
            title=title,
            description=description or "",
            labels=list(labels),
            assignee_usernames=list(assignee_usernames or []),
        )
        _MOCK_ISSUES.setdefault(gitlab_project_id, {})[iid] = issue
        logger.info("[mock] create issue %s in GitLab project %s", iid, gitlab_project_id)
        return issue

    async def update_issue(
        self,
        gitlab_project_id: int,
        iid: int,
        *,
        title: str | None = None,
        description: str | None = None,
        state_event: str | None = None,
        assignee_usernames: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> IssueInfo | None:
        issue = _MOCK_ISSUES.get(gitlab_project_id, {}).get(iid)
        if issue is None:
            logger.warning("[mock] issue %s not found in project %s", iid, gitlab_project_id)
            return None
        if title is not None:
            issue.title = title
        if description is not None:
            issue.description = description
        if labels is not None:
            issue.labels = list(labels)
        if assignee_usernames is not None:
            issue.assignee_usernames = list(assignee_usernames)
        if state_event == "close":
            issue.state = "closed"
        elif state_event == "reopen":
            issue.state = "opened"
        return issue

    async def list_issues(
        self, gitlab_project_id: int, label: str, state: str = "all"
    ) -> list[IssueInfo]:
        issues = _MOCK_ISSUES.get(gitlab_project_id, {})
        return [
            issue
            for issue in issues.values()
            if label in issue.labels and (state == "all" or issue.state == state)
        ]

    async def ensure_webhook(
        self, gitlab_project_id: int, url: str, token: str
    ) -> None:
        logger.info("[mock] webhook %s for GitLab project %s", url, gitlab_project_id)

    async def get_contributor_stats(
        self, gitlab_project_id: int, users: list[User]
    ) -> dict[int, ContributorStats]:
        # Детерминированные «реалистичные» цифры, чтобы на демо они не прыгали
        result = {}
        for u in users:
            seed = int(hashlib.md5(f"{gitlab_project_id}:{u.id}".encode()).hexdigest()[:8], 16)
            result[u.id] = ContributorStats(
                commits=5 + seed % 25,
                mrs=seed % 5,
                last_activity="2026-10-25T12:00:00Z",
            )
        return result


def get_gitlab_client() -> GitLabClient:
    if settings.use_mock_gitlab or not settings.gitlab_token:
        return MockGitLabClient()
    return RealGitLabClient()


# Локи на проект защищают от гонки «вебхук пришёл раньше, чем мы сохранили iid».
# В рамках одного процесса (uvicorn) этого достаточно; для нескольких воркеров
# дополнительно работает уникальный индекс ix_tasks_project_gitlab_iid.
_PROJECT_LOCKS: dict[int, asyncio.Lock] = {}


def _project_lock(project_id: int) -> asyncio.Lock:
    lock = _PROJECT_LOCKS.get(project_id)
    if lock is None:
        lock = asyncio.Lock()
        _PROJECT_LOCKS[project_id] = lock
    return lock


async def _project_members(db: AsyncSession, project_id: int) -> list[ProjectMember]:
    return list(
        await db.scalars(
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .options(selectinload(ProjectMember.user))
        )
    )


def _issue_labels(task: Task) -> list[str]:
    labels: list[str] = []
    if settings.gitlab_task_label:
        labels.append(settings.gitlab_task_label)
    labels.append(f"prio:{task.priority.value.lower()}")
    return labels


def _priority_from_labels(labels: list[str]) -> TaskPriority | None:
    for label in labels:
        if label.lower().startswith("prio:"):
            try:
                return TaskPriority(label.split(":", 1)[1].upper())
            except ValueError:
                continue
    return None


def _status_from_issue(issue: IssueInfo, current: TaskStatus | None) -> TaskStatus:
    if issue.state == "closed":
        return TaskStatus.DONE
    if current is None or current in (TaskStatus.DONE, TaskStatus.AI_DRAFT):
        return TaskStatus.TODO
    return current


async def _gitlab_username(db: AsyncSession, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = await db.get(User, user_id)
    return normalize_gitlab_username(user.gitlab_username) if user else None


def parse_repo_url(url: str) -> tuple[str, str]:
    """Ссылка на репозиторий -> (нормализованный web URL, path_with_namespace).

    Понимает https://gitlab.com/group/sub/repo, ...repo.git, ...repo/-/tree/main
    и SSH-вид git@gitlab.com:group/repo.git. Бросает ValueError на мусор.
    """
    url = url.strip()
    ssh = re.fullmatch(r"git@([^:]+):(.+)", url)
    if ssh:
        host, path = ssh.group(1), ssh.group(2)
        scheme = "https"
    else:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Ожидается ссылка вида https://gitlab.com/группа/репозиторий")
        scheme, host, path = parsed.scheme, parsed.netloc, parsed.path
    path = path.split("/-/")[0].strip("/").removesuffix(".git")
    if path.count("/") < 1 or any(not part for part in path.split("/")):
        raise ValueError("В ссылке должны быть группа (или пользователь) и имя репозитория")
    return f"{scheme}://{host}/{path}", path


async def attach_repository(db: AsyncSession, project: Project, repo_url: str) -> str | None:
    """Прикрепляет готовый репозиторий, созданный капитаном.

    Ссылка сохраняется всегда. ID репозитория (нужен для issues и статистики)
    узнаем через API; если не вышло — возвращаем причину, ID можно будет
    получить позже при синхронизации. Возвращает None при успехе.
    """
    web_url, path = parse_repo_url(repo_url)
    project.gitlab_repo_url = web_url
    project.gitlab_project_id = None
    problem = None
    try:
        repo = await get_gitlab_client().get_repository(path)
        project.gitlab_project_id = repo.id
        project.gitlab_repo_url = repo.web_url
    except httpx.HTTPStatusError as e:
        logger.warning("GitLab repo %s lookup failed: %s", path, e.response.status_code)
        problem = (
            "Репозиторий не найден или нет доступа: создайте его в группе команды "
            "или добавьте владельца токена GitLab в участники"
            if e.response.status_code in (401, 403, 404)
            else "GitLab ответил ошибкой, ссылка сохранена — попробуйте синхронизацию позже"
        )
    except Exception:
        logger.exception("GitLab repo %s lookup failed", path)
        problem = "GitLab сейчас недоступен, ссылка сохранена — нажмите синхронизацию позже"
    await db.commit()

    if project.gitlab_project_id:
        await ensure_project_webhook(project)
        await sync_members_to_gitlab(db, project)
    return problem


async def trigger_gitlab_repo_creation(db: AsyncSession, project: Project, users: list[User]) -> bool:
    """Создает репозиторий и приглашает участников. Ошибки GitLab не ломают создание проекта.

    Возвращает False, если репозиторий создать не удалось (его можно создать позже
    через POST /api/projects/{id}/gitlab/connect).
    """
    client = get_gitlab_client()
    try:
        repo = await client.create_repository(repo_path(project), project.name, project.description)
    except Exception:
        logger.exception("GitLab repo creation failed for project %s", project.id)
        return False
    project.gitlab_project_id = repo.id
    project.gitlab_repo_url = repo.web_url
    await db.commit()

    # Вебхук регистрируем только если задан публичный URL и секрет.
    await ensure_project_webhook(project)

    for u in users:
        if u.gitlab_username:
            await invite_to_gitlab(project, u)
    return True


async def invite_to_gitlab(project: Project, user: User) -> None:
    if not project.gitlab_project_id or not user.gitlab_username:
        return
    try:
        await get_gitlab_client().add_member(project.gitlab_project_id, user.gitlab_username)
    except Exception:
        logger.exception("GitLab invite failed for %s", user.gitlab_username)


async def ensure_project_webhook(project: Project) -> None:
    """Регистрирует вебхук проекта, если настроены URL и секрет."""
    if not (
        project.gitlab_project_id
        and settings.gitlab_webhook_url
        and settings.gitlab_webhook_secret
    ):
        return
    try:
        await get_gitlab_client().ensure_webhook(
            project.gitlab_project_id,
            settings.gitlab_webhook_url,
            settings.gitlab_webhook_secret,
        )
    except Exception:
        logger.exception("GitLab webhook registration failed for project %s", project.id)


async def sync_members_to_gitlab(db: AsyncSession, project: Project) -> tuple[int, int]:
    """Приглашает всех участников проекта с заполненным gitlab_username.

    Возвращает (приглашено, пропущено).
    """
    if not project.gitlab_project_id:
        return (0, 0)
    members = await _project_members(db, project.id)
    invited = 0
    skipped = 0
    for member in members:
        username = normalize_gitlab_username(member.user.gitlab_username)
        if not username:
            skipped += 1
            continue
        try:
            await get_gitlab_client().add_member(project.gitlab_project_id, username)
            invited += 1
        except Exception:
            logger.exception("GitLab invite failed for %s", username)
            skipped += 1
    return invited, skipped


async def sync_task_to_gitlab(db: AsyncSession, task: Task) -> None:
    """Best-effort синхронизация задачи сайта в GitLab issue.

    Никогда не бросает исключение наружу: GitLab не должен ломать API сайта.
    """
    if task.status == TaskStatus.AI_DRAFT:
        return
    try:
        project = await db.get(Project, task.project_id)
        if project is None or not project.gitlab_project_id:
            return

        username = await _gitlab_username(db, task.assignee_id)
        if task.assignee_id is None:
            assignees: list[str] | None = []
        else:
            # Если у исполнителя нет gitlab_username, не снимаем назначение
            # в GitLab: None означает «не трогать».
            assignees = [username] if username else None

        async with _project_lock(project.id):
            client = get_gitlab_client()
            if task.gitlab_issue_iid is None:
                issue = await client.create_issue(
                    project.gitlab_project_id,
                    task.title,
                    task.description or "",
                    assignees,
                    _issue_labels(task),
                )
                task.gitlab_issue_iid = issue.iid
                await db.commit()
            else:
                try:
                    issue = await client.update_issue(
                        project.gitlab_project_id,
                        task.gitlab_issue_iid,
                        title=task.title,
                        description=task.description or "",
                        labels=_issue_labels(task),
                        state_event="close" if task.status == TaskStatus.DONE else "reopen",
                        assignee_usernames=assignees,
                    )
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 404:
                        raise
                    issue = None
                if issue is None:
                    # Mock потерял состояние после рестарта или issue удалили в GitLab —
                    # создаем issue заново и обновляем iid.
                    issue = await client.create_issue(
                        project.gitlab_project_id,
                        task.title,
                        task.description or "",
                        assignees,
                        _issue_labels(task),
                    )
                    task.gitlab_issue_iid = issue.iid
                    await db.commit()
    except Exception:
        # rollback нужен, если упал commit (например, гонка с вебхуком)
        await db.rollback()
        logger.exception("GitLab task sync failed for task %s", task.id)


async def archive_task_issue(db: AsyncSession, task: Task) -> None:
    """Закрывает issue и снимает метку, чтобы импорт не воскресил удаленную задачу."""
    if task.gitlab_issue_iid is None:
        return
    try:
        project = await db.get(Project, task.project_id)
        if project is None or not project.gitlab_project_id:
            return
        async with _project_lock(project.id):
            await get_gitlab_client().update_issue(
                project.gitlab_project_id,
                task.gitlab_issue_iid,
                labels=[],
                state_event="close",
            )
    except Exception:
        await db.rollback()
        logger.exception("GitLab issue archive failed for task %s", task.id)


async def sync_issues_from_gitlab(db: AsyncSession, project: Project) -> tuple[int, int]:
    """Импортирует issues с меткой проекта в задачи. Возвращает (создано, обновлено)."""
    if not project.gitlab_project_id or not settings.gitlab_task_label:
        return (0, 0)

    members = await _project_members(db, project.id)
    usernames: dict[str, int] = {}
    for member in members:
        if member.role == ProjectRole.VIEWER:
            continue
        username = normalize_gitlab_username(member.user.gitlab_username)
        if username:
            usernames[username.lower()] = member.user_id

    async with _project_lock(project.id):
        issues = await get_gitlab_client().list_issues(
            project.gitlab_project_id, settings.gitlab_task_label
        )
        existing = list(
            await db.scalars(
                select(Task).where(
                    Task.project_id == project.id,
                    Task.gitlab_issue_iid.is_not(None),
                )
            )
        )
        by_iid = {task.gitlab_issue_iid: task for task in existing}
        created = 0
        updated = 0

        for issue in issues:
            assignee_id = next(
                (
                    usernames[name.lower()]
                    for name in issue.assignee_usernames
                    if name.lower() in usernames
                ),
                None,
            )
            priority = _priority_from_labels(issue.labels)

            task = by_iid.get(issue.iid)
            if task is None:
                task = Task(
                    project_id=project.id,
                    title=issue.title,
                    description=issue.description or None,
                    assignee_id=assignee_id,
                    status=_status_from_issue(issue, None),
                    priority=priority or TaskPriority.MEDIUM,
                    estimated_hours=1.0,
                    created_by_ai=False,
                    gitlab_issue_iid=issue.iid,
                )
                db.add(task)
                by_iid[issue.iid] = task
                created += 1
                continue

            changed = False
            if task.title != issue.title:
                task.title = issue.title
                changed = True
            description = issue.description or None
            if task.description != description:
                task.description = description
                changed = True
            new_status = _status_from_issue(issue, task.status)
            if task.status != new_status:
                task.status = new_status
                changed = True
            if priority is not None and task.priority != priority:
                task.priority = priority
                changed = True
            if assignee_id is not None and task.assignee_id != assignee_id:
                task.assignee_id = assignee_id
                changed = True
            if changed:
                updated += 1

        if created or updated:
            await db.commit()

    return created, updated


async def sync_project(db: AsyncSession, project: Project) -> dict[str, int]:
    """Полная синхронизация: участники + issues. Используется кнопкой и API."""
    await ensure_project_webhook(project)
    members_invited, members_skipped = await sync_members_to_gitlab(db, project)
    tasks_created, tasks_updated = await sync_issues_from_gitlab(db, project)
    return {
        "members_invited": members_invited,
        "members_skipped": members_skipped,
        "tasks_created": tasks_created,
        "tasks_updated": tasks_updated,
    }
