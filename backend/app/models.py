import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectRole(str, enum.Enum):
    CAPTAIN = "CAPTAIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class Specialization(str, enum.Enum):
    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"
    ML = "ML"
    DESIGN = "DESIGN"
    PM = "PM"
    FULLSTACK = "FULLSTACK"
    OTHER = "OTHER"


class TaskStatus(str, enum.Enum):
    AI_DRAFT = "AI_DRAFT"
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MaterialType(str, enum.Enum):
    GOOGLE_SLIDES = "GOOGLE_SLIDES"
    GOOGLE_DOCS = "GOOGLE_DOCS"
    FIGMA = "FIGMA"
    OTHER = "OTHER"


class HealthStatus(str, enum.Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    DELAYED = "DELAYED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    gitlab_username: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PasswordCode(Base):
    __tablename__ = "password_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    ai_health_summary: Mapped[str | None] = mapped_column(Text)
    ai_health_status: Mapped[HealthStatus] = mapped_column(
        Enum(HealthStatus), default=HealthStatus.ON_TRACK
    )
    ai_progress_score: Mapped[int] = mapped_column(default=0)
    ai_risks: Mapped[list] = mapped_column(JSON, default=list)
    gitlab_project_id: Mapped[int | None]
    gitlab_repo_url: Mapped[str | None] = mapped_column(String(512))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole), default=ProjectRole.MEMBER)
    specialization: Mapped[Specialization] = mapped_column(
        Enum(Specialization), default=Specialization.OTHER
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="members", lazy="raise")
    user: Mapped[User] = relationship(lazy="selectin")


class Task(Base):
    __tablename__ = "tasks"
    # iid issue в GitLab; nullable, чтобы старые задачи и черновики жили без GitLab
    __table_args__ = (
        Index("ix_tasks_project_gitlab_iid", "project_id", "gitlab_issue_iid", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.TODO)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    estimated_hours: Mapped[float] = mapped_column(Float, default=1.0)
    gitlab_issue_iid: Mapped[int | None]
    created_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ProjectMaterial(Base):
    __tablename__ = "project_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    type: Mapped[MaterialType] = mapped_column(Enum(MaterialType), default=MaterialType.OTHER)
    edit_url: Mapped[str] = mapped_column(String(1024))
    view_url: Mapped[str] = mapped_column(String(1024))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
