import type { HealthStatus, MaterialType, ProjectRole, ReviewState, Specialization, TaskPriority, TaskStatus } from "@/api/types";

export const ROLE_LABELS: Record<ProjectRole, string> = {
  CAPTAIN: "Капитан",
  MEMBER: "Участник",
  VIEWER: "Наблюдатель",
};

export const SPEC_LABELS: Record<Specialization, string> = {
  BACKEND: "Backend",
  FRONTEND: "Frontend",
  ML: "ML",
  DESIGN: "Design",
  PM: "PM",
  FULLSTACK: "Fullstack",
  OTHER: "Другое",
};

export const STATUS_LABELS: Record<TaskStatus, string> = {
  AI_DRAFT: "Черновик ИИ",
  TODO: "К выполнению",
  IN_PROGRESS: "В работе",
  REVIEW: "На ревью",
  DONE: "Готово",
};

export const BOARD_COLUMNS: TaskStatus[] = ["TODO", "IN_PROGRESS", "REVIEW", "DONE"];

/** Следующий шаг для кнопки «в один клик» в личном кабинете */
export const NEXT_STATUS: Partial<Record<TaskStatus, { status: TaskStatus; label: string }>> = {
  TODO: { status: "IN_PROGRESS", label: "Взять в работу" },
  IN_PROGRESS: { status: "REVIEW", label: "На ревью" },
  REVIEW: { status: "DONE", label: "Готово" },
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  LOW: "Низкий",
  MEDIUM: "Средний",
  HIGH: "Высокий",
  CRITICAL: "Критичный",
};

export const PRIORITY_COLORS: Record<TaskPriority, string> = {
  LOW: "bg-slate-100 text-slate-600",
  MEDIUM: "bg-sky-100 text-sky-700",
  HIGH: "bg-amber-100 text-amber-800",
  CRITICAL: "bg-red-100 text-red-700",
};

export const HEALTH_LABELS: Record<HealthStatus, { label: string; className: string }> = {
  ON_TRACK: { label: "On Track", className: "bg-emerald-100 text-emerald-700" },
  AT_RISK: { label: "At Risk", className: "bg-amber-100 text-amber-800" },
  DELAYED: { label: "Delayed", className: "bg-red-100 text-red-700" },
};

export const MATERIAL_LABELS: Record<MaterialType, string> = {
  GOOGLE_SLIDES: "Google Презентация",
  GOOGLE_DOCS: "Google Документ",
  FIGMA: "Figma",
  OTHER: "Ссылка",
};

export const REVIEW_STATE_LABELS: Record<ReviewState, { label: string; className: string }> = {
  AI_REVIEWING: { label: "ИИ проверяет…", className: "bg-violet-100 text-violet-700" },
  CHANGES_REQUESTED: { label: "Замечания ИИ", className: "bg-amber-100 text-amber-800" },
  AWAITING_CAPTAIN: { label: "Ждет капитана", className: "bg-sky-100 text-sky-700" },
  CAPTAIN_REJECTED: { label: "Отклонено капитаном", className: "bg-red-100 text-red-700" },
  MERGED: { label: "MR влит", className: "bg-emerald-100 text-emerald-700" },
};

export const REVIEW_VERDICT_LABELS: Record<string, { label: string; className: string }> = {
  APPROVE: { label: "ИИ одобрил", className: "bg-emerald-100 text-emerald-700" },
  CHANGES_REQUESTED: { label: "ИИ: нужны исправления", className: "bg-amber-100 text-amber-800" },
  SKIPPED: { label: "ИИ недоступен", className: "bg-slate-100 text-slate-700" },
  MERGED: { label: "Капитан влил MR", className: "bg-emerald-100 text-emerald-700" },
  REJECTED: { label: "Капитан отклонил", className: "bg-red-100 text-red-700" },
};
