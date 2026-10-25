// Зеркало backend/app/schemas.py — при изменении контрактов правьте оба файла

export type ProjectRole = "CAPTAIN" | "MEMBER" | "VIEWER";
export type Specialization = "BACKEND" | "FRONTEND" | "ML" | "DESIGN" | "PM" | "FULLSTACK" | "OTHER";
export type TaskStatus = "AI_DRAFT" | "TODO" | "IN_PROGRESS" | "REVIEW" | "DONE";
export type TaskPriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type MaterialType = "GOOGLE_SLIDES" | "GOOGLE_DOCS" | "FIGMA" | "OTHER";
export type ReviewState = "AI_REVIEWING" | "CHANGES_REQUESTED" | "AWAITING_CAPTAIN" | "CAPTAIN_REJECTED" | "MERGED";
export type HealthStatus = "ON_TRACK" | "AT_RISK" | "DELAYED";

export interface User {
  id: number;
  email: string;
  name: string;
  gitlab_username: string | null;
  avatar_url: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface PasswordCodeSent {
  message: string;
  debug_code: string | null;
}

export interface Member {
  user_id: number;
  name: string;
  email: string;
  gitlab_username: string | null;
  avatar_url: string | null;
  role: ProjectRole;
  specialization: Specialization;
  joined_at: string;
}

export interface ProjectSummary {
  id: number;
  name: string;
  description: string;
  ai_progress_score: number;
  ai_health_status: HealthStatus;
  gitlab_repo_url: string | null;
  members_count: number;
  my_role: ProjectRole;
  created_at: string;
}

export interface ProjectDetail extends ProjectSummary {
  ai_health_summary: string | null;
  ai_risks: string[];
  gitlab_project_id: number | null;
  members: Member[];
}

export interface Task {
  id: number;
  project_id: number;
  title: string;
  description: string | null;
  assignee_id: number | null;
  status: TaskStatus;
  priority: TaskPriority;
  estimated_hours: number;
  created_by_ai: boolean;
  /** iid issue в GitLab; null — задача еще не синхронизирована */
  gitlab_issue_iid: number | null;
  /** Ветка задачи в GitLab (появляется после «Взять в работу») */
  branch_name: string | null;
  review_state: ReviewState | null;
  gitlab_mr_iid: number | null;
  created_at: string;
  updated_at: string;
}

export interface TaskInput {
  title: string;
  description?: string | null;
  assignee_id?: number | null;
  priority?: TaskPriority;
  estimated_hours?: number;
}

export interface DraftGroup {
  assignee_id: number | null;
  assignee_name: string;
  specialization: Specialization | null;
  tasks: Task[];
}

export interface ApprovedTask extends TaskInput {
  id: number | null;
}

export interface AIStatus {
  ai_health_summary: string | null;
  ai_health_status: HealthStatus;
  ai_progress_score: number;
  ai_risks: string[];
}

export interface Material {
  id: number;
  title: string;
  type: MaterialType;
  target_url: string;
  access_mode: "EDIT" | "VIEW";
  can_edit: boolean;
  created_at: string;
}

export interface MemberStats {
  user_id: number;
  name: string;
  role: ProjectRole;
  specialization: Specialization;
  tasks_assigned: number;
  tasks_in_progress: number;
  tasks_completed: number;
  hours_completed: number;
  gitlab_commits: number;
  gitlab_mrs: number;
  last_activity: string | null;
  contribution_percent: number;
}

export interface Analytics {
  project_id: number;
  total_tasks: number;
  completed_tasks: number;
  total_commits: number;
  total_mrs: number;
  members_stats: MemberStats[];
}

export interface GitLabAttach {
  /** null — ссылка сохранена, но GitLab пока не подтвердил репозиторий */
  gitlab_project_id: number | null;
  gitlab_repo_url: string;
  warning: string | null;
}

export interface GitLabSync {
  members_invited: number;
  members_skipped: number;
  tasks_created: number;
  tasks_updated: number;
}

export interface ReviewIssue {
  file: string | null;
  line: number | null;
  comment: string;
}

export interface TaskReview {
  id: number;
  reviewer: "AI" | "CAPTAIN";
  /** APPROVE | CHANGES_REQUESTED | SKIPPED | MERGED | REJECTED */
  verdict: string;
  summary: string;
  issues: ReviewIssue[];
  commit_sha: string | null;
  author_id: number | null;
  created_at: string;
}

export interface TaskReviews {
  task: Task;
  mr_url: string | null;
  reviews: TaskReview[];
}
