import { BarChart3, GitBranch, LayoutDashboard, ListTodo, Trash2, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { projectsApi } from "@/api/endpoints";
import type { ProjectDetail } from "@/api/types";
import { ProjectContext } from "@/context/ProjectContext";
import { ROLE_LABELS } from "@/lib/labels";
import { cn, errorMessage } from "@/lib/utils";
import { AttachRepoModal } from "./project/AttachRepoModal";
import { DeleteProjectModal } from "./project/DeleteProjectModal";
import { Badge, Button, ErrorText, Spinner } from "./ui";

const TABS = [
  { to: "", label: "Доска", icon: LayoutDashboard, end: true },
  { to: "my-workspace", label: "Мои задачи", icon: ListTodo },
  { to: "team", label: "Команда", icon: Users },
  { to: "analytics", label: "Аналитика", icon: BarChart3 },
];

export default function ProjectLayout() {
  const projectId = Number(useParams().id);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState("");
  const [repoModalOpen, setRepoModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const reload = useCallback(async () => {
    try {
      setProject(await projectsApi.get(projectId));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [projectId]);

  useEffect(() => {
    setProject(null);
    reload();
  }, [reload]);

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!project) return <Spinner />;

  const isCaptain = project.my_role === "CAPTAIN";
  const canEdit = project.my_role !== "VIEWER";

  return (
    <ProjectContext.Provider value={{ project, reload, isCaptain, canEdit }}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold">{project.name}</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
            <Badge>{ROLE_LABELS[project.my_role]}</Badge>
            {project.gitlab_repo_url ? (
              <a href={project.gitlab_repo_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-slate-900">
                <GitBranch className="h-4 w-4 text-orange-500" />
                GitLab подключен
              </a>
            ) : (
              <span className="inline-flex items-center gap-1">
                <GitBranch className="h-4 w-4" /> GitLab не подключен
              </span>
            )}
            {isCaptain && (
              <Button size="sm" variant="outline" onClick={() => setRepoModalOpen(true)}>
                {project.gitlab_repo_url ? "Изменить" : "Прикрепить репозиторий"}
              </Button>
            )}
          </div>
        </div>
        {isCaptain && (
          <Button variant="outline" size="sm" onClick={() => setDeleting(true)} className="text-red-600 hover:bg-red-50">
            <Trash2 className="h-4 w-4" /> Удалить проект
          </Button>
        )}
      </div>
      {isCaptain && <DeleteProjectModal project={project} open={deleting} onClose={() => setDeleting(false)} />}

      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={label}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium",
                isActive ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-900",
              )
            }
          >
            <Icon className="h-4 w-4" /> {label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
      {isCaptain && <AttachRepoModal open={repoModalOpen} onClose={() => setRepoModalOpen(false)} />}
    </ProjectContext.Provider>
  );
}
