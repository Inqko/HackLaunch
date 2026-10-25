from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import (
    HealthStatus,
    MaterialType,
    ProjectRole,
    Specialization,
    TaskPriority,
    TaskStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth / Users ---

class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)
    password: str = Field(min_length=6)
    gitlab_username: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    gitlab_username: str | None


class UserUpdate(BaseModel):
    name: str | None = None
    gitlab_username: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Projects / Members ---

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    auto_create_gitlab: bool = True
    specialization: Specialization = Specialization.PM


class MemberOut(BaseModel):
    user_id: int
    name: str
    email: str
    gitlab_username: str | None
    role: ProjectRole
    specialization: Specialization
    joined_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr
    role: ProjectRole = ProjectRole.MEMBER
    specialization: Specialization = Specialization.OTHER


class MemberUpdate(BaseModel):
    role: ProjectRole | None = None
    specialization: Specialization | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    ai_progress_score: int
    ai_health_status: HealthStatus
    gitlab_repo_url: str | None
    members_count: int
    my_role: ProjectRole
    created_at: datetime


class ProjectDetail(ProjectOut):
    ai_health_summary: str | None
    ai_risks: list[str]
    gitlab_project_id: int | None
    members: list[MemberOut]


# --- Tasks ---

class TaskOut(ORMModel):
    id: int
    project_id: int
    title: str
    description: str | None
    assignee_id: int | None
    status: TaskStatus
    priority: TaskPriority
    estimated_hours: float
    created_by_ai: bool
    # Добавлено вместе с мостом GitLab; nullable — контракт обратно совместим
    gitlab_issue_iid: int | None = None
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    assignee_id: int | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_hours: float = 1.0


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: int | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    estimated_hours: float | None = None


class DraftGroup(BaseModel):
    assignee_id: int | None
    assignee_name: str
    specialization: Specialization | None
    tasks: list[TaskOut]


class ApprovedTask(BaseModel):
    id: int | None = None  # None — Капитан добавил свою задачу вручную
    title: str = Field(min_length=1)
    description: str | None = None
    assignee_id: int | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_hours: float = 1.0


class ApproveBatchIn(BaseModel):
    approved_tasks: list[ApprovedTask] = []
    rejected_task_ids: list[int] = []


class ApproveBatchOut(BaseModel):
    approved: list[TaskOut]
    rejected_count: int


# --- AI ---

class GenerateTasksIn(BaseModel):
    additional_context: str | None = None


class AIStatusOut(BaseModel):
    ai_health_summary: str | None
    ai_health_status: HealthStatus
    ai_progress_score: int
    ai_risks: list[str]


# --- GitLab ---

class GitLabSyncOut(BaseModel):
    members_invited: int
    members_skipped: int
    tasks_created: int
    tasks_updated: int


# --- Materials ---

class MaterialCreate(BaseModel):
    title: str = Field(min_length=1)
    type: MaterialType
    edit_url: str = Field(min_length=1)
    view_url: str = Field(min_length=1)


class MaterialOut(BaseModel):
    id: int
    title: str
    type: MaterialType
    target_url: str
    access_mode: Literal["EDIT", "VIEW"]
    can_edit: bool
    created_at: datetime


# --- Analytics ---

class MemberStats(BaseModel):
    user_id: int
    name: str
    role: ProjectRole
    specialization: Specialization
    tasks_assigned: int
    tasks_in_progress: int
    tasks_completed: int
    hours_completed: float
    gitlab_commits: int
    gitlab_mrs: int
    last_activity: str | None
    contribution_percent: float


class AnalyticsOut(BaseModel):
    project_id: int
    total_tasks: int
    completed_tasks: int
    total_commits: int
    total_mrs: int
    members_stats: list[MemberStats]
