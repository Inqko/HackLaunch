import { http } from "./client";
import type {
  AIStatus,
  Analytics,
  ApprovedTask,
  DraftGroup,
  Material,
  MaterialType,
  Member,
  ProjectDetail,
  ProjectRole,
  ProjectSummary,
  Specialization,
  Task,
  TaskInput,
  TaskStatus,
  TokenResponse,
  User,
} from "./types";

export const authApi = {
  register: (data: { email: string; name: string; password: string; gitlab_username?: string }) =>
    http.post<TokenResponse>("/api/auth/register", data),
  login: (data: { email: string; password: string }) => http.post<TokenResponse>("/api/auth/login", data),
  me: () => http.get<User>("/api/users/me"),
  updateMe: (data: { name?: string; gitlab_username?: string | null }) => http.patch<User>("/api/users/me", data),
};

export const avatarApi = {
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return http.upload<User>("/api/users/me/avatar", form);
  },
  remove: () => http.del<User>("/api/users/me/avatar"),
};

export const projectsApi = {
  list: () => http.get<ProjectSummary[]>("/api/projects"),
  create: (data: { name: string; description: string; auto_create_gitlab: boolean; specialization: Specialization }) =>
    http.post<ProjectDetail>("/api/projects", data),
  get: (id: number) => http.get<ProjectDetail>(`/api/projects/${id}`),
  addMember: (id: number, data: { email: string; role: ProjectRole; specialization: Specialization }) =>
    http.post<Member>(`/api/projects/${id}/members`, data),
  updateMember: (id: number, userId: number, data: { role?: ProjectRole; specialization?: Specialization }) =>
    http.patch<Member>(`/api/projects/${id}/members/${userId}`, data),
  removeMember: (id: number, userId: number) => http.del(`/api/projects/${id}/members/${userId}`),
};

export const tasksApi = {
  list: (projectId: number) => http.get<Task[]>(`/api/projects/${projectId}/tasks`),
  my: (projectId: number) => http.get<Task[]>(`/api/projects/${projectId}/tasks/my`),
  create: (projectId: number, data: TaskInput) => http.post<Task>(`/api/projects/${projectId}/tasks`, data),
  update: (taskId: number, data: Partial<TaskInput> & { status?: TaskStatus }) =>
    http.patch<Task>(`/api/tasks/${taskId}`, data),
  remove: (taskId: number) => http.del(`/api/tasks/${taskId}`),
  drafts: (projectId: number) => http.get<DraftGroup[]>(`/api/projects/${projectId}/tasks/drafts`),
  approveBatch: (projectId: number, data: { approved_tasks: ApprovedTask[]; rejected_task_ids: number[] }) =>
    http.post<{ approved: Task[]; rejected_count: number }>(`/api/projects/${projectId}/tasks/approve-batch`, data),
};

export const aiApi = {
  generateTasks: (projectId: number, additional_context?: string) =>
    http.post<Task[]>(`/api/projects/${projectId}/ai/generate-tasks`, { additional_context }),
  refreshStatus: (projectId: number) => http.post<AIStatus>(`/api/projects/${projectId}/ai/refresh-status`),
};

export const materialsApi = {
  list: (projectId: number) => http.get<Material[]>(`/api/projects/${projectId}/materials`),
  create: (projectId: number, data: { title: string; type: MaterialType; edit_url: string; view_url: string }) =>
    http.post<Material>(`/api/projects/${projectId}/materials`, data),
  remove: (projectId: number, materialId: number) => http.del(`/api/projects/${projectId}/materials/${materialId}`),
};

export const analyticsApi = {
  get: (projectId: number) => http.get<Analytics>(`/api/projects/${projectId}/analytics`),
  export: (projectId: number, format: "csv" | "json") =>
    http.download(`/api/projects/${projectId}/analytics/export?format=${format}`, `analytics.${format}`),
};
