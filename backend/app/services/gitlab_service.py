"""Интеграция с GitLab REST API v4 (Участник 3).

Без токена или с USE_MOCK_GITLAB=true используется MockGitLabClient,
чтобы демо работало без сети.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Project, User

logger = logging.getLogger(__name__)

DEVELOPER_ACCESS_LEVEL = 30


@dataclass
class RepoInfo:
    id: int
    web_url: str


@dataclass
class ContributorStats:
    commits: int = 0
    mrs: int = 0
    last_activity: str | None = None


class GitLabClient(Protocol):
    async def create_repository(self, path: str, name: str, description: str) -> RepoInfo: ...

    async def add_member(self, gitlab_project_id: int, username: str) -> None: ...

    async def get_contributor_stats(
        self, gitlab_project_id: int, users: list[User]
    ) -> dict[int, ContributorStats]: ...


def repo_path(project: Project) -> str:
    # GitLab path допускает только латиницу; кириллица отбрасывается, id гарантирует уникальность
    slug = re.sub(r"[^a-z0-9]+", "-", project.name.lower()).strip("-") or "project"
    return f"{slug}-{project.id}"


class RealGitLabClient:
    def __init__(self) -> None:
        self._base = f"{settings.gitlab_url.rstrip('/')}/api/v4"
        self._headers = {"PRIVATE-TOKEN": settings.gitlab_token}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, headers=self._headers, timeout=15)

    async def create_repository(self, path: str, name: str, description: str) -> RepoInfo:
        body = {
            "name": name,
            "path": path,
            "description": description[:2000],
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

    async def add_member(self, gitlab_project_id: int, username: str) -> None:
        async with self._client() as client:
            resp = await client.get("/users", params={"username": username})
            resp.raise_for_status()
            found = resp.json()
            if not found:
                logger.warning("GitLab user %s not found", username)
                return
            resp = await client.post(
                f"/projects/{gitlab_project_id}/members",
                json={"user_id": found[0]["id"], "access_level": DEVELOPER_ACCESS_LEVEL},
            )
            if resp.status_code != 409:  # 409 — уже участник
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

        # Коммиты в API не содержат username, сопоставляем по email / имени
        for c in commits:
            for u in users:
                keys = {u.email.lower(), u.name.lower(), (u.gitlab_username or "").lower()}
                if c.get("author_email", "").lower() in keys or c.get("author_name", "").lower() in keys:
                    s = stats[u.id]
                    s.commits += 1
                    s.last_activity = max(s.last_activity or "", c.get("committed_date") or "") or None
                    break
        for mr in mrs:
            author = (mr.get("author") or {}).get("username", "").lower()
            for u in users:
                if u.gitlab_username and u.gitlab_username.lower() == author:
                    stats[u.id].mrs += 1
                    break
        return stats


class MockGitLabClient:
    async def create_repository(self, path: str, name: str, description: str) -> RepoInfo:
        digest = int(hashlib.md5(path.encode()).hexdigest()[:6], 16)
        return RepoInfo(
            id=100000 + digest % 900000,
            web_url=f"{settings.gitlab_url.rstrip('/')}/hacklaunch-demo/{path}",
        )

    async def add_member(self, gitlab_project_id: int, username: str) -> None:
        logger.info("[mock] add %s to GitLab project %s", username, gitlab_project_id)

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


async def trigger_gitlab_repo_creation(db: AsyncSession, project: Project, users: list[User]) -> None:
    """Создает репозиторий и приглашает участников. Ошибки GitLab не ломают создание проекта."""
    client = get_gitlab_client()
    try:
        repo = await client.create_repository(repo_path(project), project.name, project.description)
    except Exception:
        logger.exception("GitLab repo creation failed for project %s", project.id)
        return
    project.gitlab_project_id = repo.id
    project.gitlab_repo_url = repo.web_url
    await db.commit()
    for u in users:
        if u.gitlab_username:
            await invite_to_gitlab(project, u)


async def invite_to_gitlab(project: Project, user: User) -> None:
    if not project.gitlab_project_id or not user.gitlab_username:
        return
    try:
        await get_gitlab_client().add_member(project.gitlab_project_id, user.gitlab_username)
    except Exception:
        logger.exception("GitLab invite failed for %s", user.gitlab_username)
