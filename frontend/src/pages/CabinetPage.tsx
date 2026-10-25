import {
  CheckCircle2,
  Clock,
  FolderKanban,
  GitBranch,
  ImagePlus,
  ListTodo,
  Mail,
  Pencil,
  Play,
  Square,
  Timer,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { projectsApi, tasksApi } from "@/api/endpoints";
import type { ProjectSummary, Task, TaskPriority, TaskStatus } from "@/api/types";
import { Avatar } from "@/components/Avatar";
import { AvatarCropModal } from "@/components/AvatarCropModal";
import { Badge, Button, Card, ErrorText, Input, Label, Modal, Select, Spinner } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { formatClock, formatTracked, useWorkTimer } from "@/hooks/useWorkTimer";
import { NEXT_STATUS, PRIORITY_COLORS, PRIORITY_LABELS, ROLE_LABELS, STATUS_LABELS } from "@/lib/labels";
import { cn, errorMessage } from "@/lib/utils";

interface TaskWithProject {
  task: Task;
  project: ProjectSummary;
}

const STATUS_ORDER: TaskStatus[] = ["TODO", "IN_PROGRESS", "REVIEW", "DONE"];
const PRIORITY_ORDER: Record<TaskPriority, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

function isToday(iso: string): boolean {
  const date = new Date(iso);
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

export default function CabinetPage() {
  const { user } = useAuth();
  const timer = useWorkTimer();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [items, setItems] = useState<TaskWithProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [projectFilter, setProjectFilter] = useState<number | "">("");
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await projectsApi.list();
      const grouped = await Promise.all(
        list.map(async (project) => {
          try {
            const tasks = await tasksApi.my(project.id);
            return tasks.map((task) => ({ task, project }));
          } catch {
            return [] as TaskWithProject[];
          }
        }),
      );
      setProjects(list);
      setItems(grouped.flat());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(
    () => (projectFilter === "" ? items : items.filter((item) => item.project.id === projectFilter)),
    [items, projectFilter],
  );

  const doneToday = filtered.filter((item) => item.task.status === "DONE" && isToday(item.task.updated_at));
  const open = filtered.filter((item) => item.task.status !== "DONE");
  const inProgress = filtered.filter((item) => item.task.status === "IN_PROGRESS");
  const hoursLeft = open.reduce((sum, item) => sum + item.task.estimated_hours, 0);

  const grouped = STATUS_ORDER.map((status) => ({
    status,
    tasks: filtered
      .filter((item) => item.task.status === status)
      .sort((a, b) => PRIORITY_ORDER[a.task.priority] - PRIORITY_ORDER[b.task.priority]),
  })).filter((group) => group.tasks.length > 0);

  const advance = async (item: TaskWithProject) => {
    const next = NEXT_STATUS[item.task.status];
    if (!next) return;
    setError("");
    try {
      const updated = await tasksApi.update(item.task.id, { status: next.status });
      setItems((prev) => prev.map((row) => (row.task.id === updated.id ? { ...row, task: updated } : row)));
      if (next.status === "DONE" && timer.active?.taskId === updated.id) timer.stop();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Личный кабинет</h1>
          <p className="text-sm text-slate-500">Профиль, задачи и личная статистика работы</p>
        </div>
        <Select
          className="w-full sm:w-64"
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">Все проекты</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </Select>
      </div>

      <ErrorText>{error}</ErrorText>

      <ProfileCard onEdit={() => setEditing(true)} />

      {timer.active && (
        <Card className="flex flex-wrap items-center justify-between gap-4 border-indigo-200 bg-gradient-to-r from-indigo-50 to-violet-50">
          <div className="flex min-w-0 items-center gap-3">
            <span className="relative flex h-3 w-3 shrink-0">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-indigo-600" />
            </span>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-indigo-600">Сейчас в работе</p>
              <p className="truncate font-semibold">{timer.active.title}</p>
              {timer.active.projectName && <p className="truncate text-xs text-slate-500">{timer.active.projectName}</p>}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-2xl font-semibold tabular-nums">{formatClock(timer.activeSeconds)}</span>
            <Button variant="destructive" size="sm" onClick={timer.stop}>
              <Square className="h-3.5 w-3.5" /> Стоп
            </Button>
          </div>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={FolderKanban} label="Проектов" value={projects.length} tone="text-indigo-500" />
        <Stat icon={ListTodo} label="Открытых задач" value={open.length} tone="text-sky-500" />
        <Stat icon={Timer} label="В работе" value={inProgress.length} tone="text-violet-500" />
        <Stat icon={CheckCircle2} label="Выполнено сегодня" value={doneToday.length} tone="text-emerald-500" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Timer className="h-8 w-8 text-indigo-500" />
            <div>
              <p className="text-sm text-slate-500">Отработано сегодня</p>
              <p className="text-xl font-semibold">{formatTracked(timer.todayTotal)}</p>
            </div>
          </div>
          <span className="text-xs text-slate-400">по таймеру</span>
        </Card>
        <Card className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Clock className="h-8 w-8 text-amber-500" />
            <div>
              <p className="text-sm text-slate-500">Осталось по оценке</p>
              <p className="text-xl font-semibold">{hoursLeft} ч</p>
            </div>
          </div>
          <span className="text-xs text-slate-400">{open.length} задач</span>
        </Card>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : (
        <>
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Мои задачи</h2>
              <span className="text-sm text-slate-500">{filtered.length} всего</span>
            </div>

            {grouped.length === 0 && (
              <Card className="text-center text-slate-500">
                Задач пока нет. Создайте проект или попросите капитана назначить задачу.
              </Card>
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              {grouped.map(({ status, tasks }) => (
                <Card key={status} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold">{STATUS_LABELS[status]}</h3>
                    <Badge>{tasks.length}</Badge>
                  </div>
                  <div className="space-y-2">
                    {tasks.map((item) => (
                      <TaskRow key={item.task.id} item={item} timer={timer} onAdvance={() => advance(item)} />
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Мои проекты</h2>
            {projects.length === 0 ? (
              <Card className="text-center text-slate-500">
                Вы пока не участвуете ни в одном проекте. <Link to="/projects" className="text-indigo-600 hover:underline">Перейти к проектам</Link>
              </Card>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {projects.map((project) => (
                  <Link key={project.id} to={`/projects/${project.id}`}>
                    <Card className="flex h-full items-center justify-between gap-3 transition hover:border-slate-300 hover:shadow-md">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{project.name}</p>
                        <p className="mt-1 line-clamp-1 text-xs text-slate-500">{project.description}</p>
                      </div>
                      <Badge>{ROLE_LABELS[project.my_role]}</Badge>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {user && (
        <EditProfileModal
          open={editing}
          onClose={() => setEditing(false)}
          initialName={user.name}
          initialGitlab={user.gitlab_username ?? ""}
        />
      )}
    </div>
  );
}

const AVATAR_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
// Исходник только кадрируется в браузере, на сервер уходит квадрат 512×512
const AVATAR_SOURCE_MAX_MB = 20;

function ProfileCard({ onEdit }: { onEdit: () => void }) {
  const { user, uploadAvatar, removeAvatar } = useAuth();
  const [busy, setBusy] = useState(false);
  const [avatarError, setAvatarError] = useState("");
  const [cropFile, setCropFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!user) return null;

  const run = async (action: () => Promise<unknown>) => {
    setAvatarError("");
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setAvatarError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!AVATAR_TYPES.includes(file.type)) {
      setAvatarError("Поддерживаются только JPEG, PNG, WebP и GIF");
      return;
    }
    if (file.size > AVATAR_SOURCE_MAX_MB * 1024 * 1024) {
      setAvatarError(`Файл больше ${AVATAR_SOURCE_MAX_MB} МБ`);
      return;
    }
    setAvatarError("");
    setCropFile(file);
  };

  const handleCropped = async (cropped: File) => {
    // Ошибку загрузки показывает само окно кадрирования, поэтому здесь её не ловим
    await uploadAvatar(cropped);
    setCropFile(null);
  };

  const handleDelete = () => {
    if (confirm("Удалить фотографию профиля?")) void run(removeAvatar);
  };

  return (
    <Card className="flex flex-wrap items-center gap-5">
      <div className="flex shrink-0 flex-col items-center gap-2">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          className="group relative rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
          title="Загрузить фото"
        >
          <Avatar src={user.avatar_url} name={user.name} className="h-20 w-20 text-2xl" />
          <span
            className={cn(
              "absolute inset-0 flex items-center justify-center rounded-full bg-black/40 transition-opacity",
              busy ? "opacity-100" : "opacity-0 group-hover:opacity-100",
            )}
          >
            {busy ? <Spinner /> : <ImagePlus className="h-5 w-5 text-white" />}
          </span>
        </button>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={() => inputRef.current?.click()} disabled={busy} title="Загрузить фото">
            <ImagePlus className="h-4 w-4" />
          </Button>
          {user.avatar_url && (
            <Button variant="ghost" size="sm" onClick={handleDelete} disabled={busy} title="Удалить фото">
              <Trash2 className="h-4 w-4 text-red-500" />
            </Button>
          )}
        </div>
        <input ref={inputRef} type="file" accept={AVATAR_TYPES.join(",")} className="hidden" onChange={handleFile} />
        <AvatarCropModal file={cropFile} onClose={() => setCropFile(null)} onConfirm={handleCropped} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xl font-semibold">{user.name}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <Mail className="h-4 w-4" /> {user.email}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <GitBranch className="h-4 w-4 text-orange-500" />
            {user.gitlab_username ? `@${user.gitlab_username}` : "GitLab не привязан"}
          </span>
        </div>
        {avatarError && <div className="mt-2"><ErrorText>{avatarError}</ErrorText></div>}
      </div>
      <Button variant="outline" onClick={onEdit}>
        <Pencil className="h-4 w-4" /> Редактировать профиль
      </Button>
    </Card>
  );
}

function TaskRow({
  item,
  timer,
  onAdvance,
}: {
  item: TaskWithProject;
  timer: ReturnType<typeof useWorkTimer>;
  onAdvance: () => void;
}) {
  const { task, project } = item;
  const isActive = timer.active?.taskId === task.id;
  const tracked = timer.secondsForTask(task.id);
  const next = NEXT_STATUS[task.status];

  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 font-medium">{task.title}</p>
        <span className="shrink-0 font-mono text-xs text-slate-500">{formatTracked(tracked)}</span>
      </div>
      {task.description && <p className="mt-1 line-clamp-2 text-sm text-slate-500">{task.description}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Link to={`/projects/${project.id}`} className="text-xs text-indigo-600 hover:underline">
          {project.name}
        </Link>
        <Badge className={PRIORITY_COLORS[task.priority]}>{PRIORITY_LABELS[task.priority]}</Badge>
        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
          <Clock className="h-3 w-3" /> {task.estimated_hours} ч
        </span>
      </div>
      {task.status !== "DONE" && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant={isActive ? "destructive" : "outline"}
            onClick={() => timer.toggle(task.id, { title: task.title, projectName: project.name })}
          >
            {isActive ? <Square className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            {isActive ? "Стоп" : "Старт"}
          </Button>
          {next && (
            <Button size="sm" variant="ghost" onClick={onAdvance}>
              {next.label}
            </Button>
          )}
        </div>
      )}
      {task.status === "DONE" && isToday(task.updated_at) && (
        <p className="mt-2 text-xs font-medium text-emerald-600">Выполнено сегодня</p>
      )}
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Clock;
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <Card className="flex items-center gap-3">
      <Icon className={`h-8 w-8 ${tone}`} />
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-sm text-slate-500">{label}</p>
      </div>
    </Card>
  );
}

function EditProfileModal({
  open,
  onClose,
  initialName,
  initialGitlab,
}: {
  open: boolean;
  onClose: () => void;
  initialName: string;
  initialGitlab: string;
}) {
  const { updateProfile } = useAuth();
  const [name, setName] = useState(initialName);
  const [gitlab, setGitlab] = useState(initialGitlab);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(initialName);
    setGitlab(initialGitlab);
    setError("");
    setBusy(false);
  }, [open, initialName, initialGitlab]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await updateProfile({ name: name.trim(), gitlab_username: gitlab.trim() || null });
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="Редактировать профиль" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label>Имя</Label>
          <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Как вас зовут" />
        </div>
        <div>
          <Label>GitLab username</Label>
          <Input
            value={gitlab}
            onChange={(e) => setGitlab(e.target.value)}
            placeholder="username без @"
          />
          <p className="mt-1 text-xs text-slate-500">Нужен, чтобы капитан мог пригласить вас в репозиторий проекта.</p>
        </div>
        <ErrorText>{error}</ErrorText>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" disabled={busy}>
            {busy ? "Сохраняем..." : "Сохранить"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
