import { Bot, CheckCircle2, Clock, GitBranch, ListTodo, Timer } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { reviewApi, tasksApi } from "@/api/endpoints";
import type { Task, TaskPriority } from "@/api/types";
import { ReviewModal } from "@/components/project/ReviewModal";
import { Badge, Button, Card, ErrorText, Select } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { NEXT_STATUS, PRIORITY_COLORS, PRIORITY_LABELS, REVIEW_STATE_LABELS, STATUS_LABELS } from "@/lib/labels";
import { errorMessage } from "@/lib/utils";

const PRIORITY_ORDER: Record<TaskPriority, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

export default function MyWorkspacePage() {
  const { project, reload, canEdit } = useProject();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [priority, setPriority] = useState<TaskPriority | "">("");
  const [error, setError] = useState("");
  const [reviewTask, setReviewTask] = useState<Task | null>(null);
  // С репозиторием «На ревью» запускает ИИ-ревью, а «Готово» решает капитан после merge
  const hasRepo = Boolean(project.gitlab_project_id);

  const load = useCallback(async () => {
    try {
      setTasks(await tasksApi.my(project.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [project.id]);

  useEffect(() => {
    load();
  }, [load]);

  const reviewing = tasks.some((t) => t.review_state === "AI_REVIEWING");
  useEffect(() => {
    if (!reviewing) return;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [reviewing, load]);

  const nextStep = (task: Task) => (hasRepo && task.status === "REVIEW" ? undefined : NEXT_STATUS[task.status]);

  const advance = async (task: Task) => {
    const next = nextStep(task);
    if (!next) return;
    try {
      if (hasRepo && task.status === "IN_PROGRESS") await reviewApi.submit(task.id);
      else await tasksApi.update(task.id, { status: next.status });
      await load();
      reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  if (!canEdit) {
    return <Card className="text-slate-500">У наблюдателя нет личных задач.</Card>;
  }

  const done = tasks.filter((t) => t.status === "DONE");
  const open = tasks
    .filter((t) => t.status !== "DONE" && (!priority || t.priority === priority))
    .sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);
  const hoursLeft = open.reduce((s, t) => s + t.estimated_hours, 0);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon={ListTodo} label="Открытых задач" value={tasks.length - done.length} />
        <Stat icon={CheckCircle2} label="Выполнено" value={done.length} />
        <Stat icon={Timer} label="Осталось часов" value={hoursLeft} />
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Мои задачи</h2>
        <Select className="w-48" value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority | "")}>
          <option value="">Все приоритеты</option>
          {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      <ErrorText>{error}</ErrorText>

      <div className="space-y-2">
        {open.map((t) => (
          <Card key={t.id} className="flex flex-wrap items-center gap-4 p-4">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{t.title}</p>
              {t.description && <p className="mt-1 whitespace-pre-line text-sm text-slate-600">{t.description}</p>}
              {t.status === "IN_PROGRESS" && t.branch_name && (
                <p className="mt-2 flex flex-wrap items-center gap-1 text-xs text-slate-500">
                  <GitBranch className="h-3.5 w-3.5" /> Работайте в ветке задачи — push в нее отправит задачу на ИИ-ревью:
                  <code className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-700">
                    git fetch origin && git switch {t.branch_name}
                  </code>
                </p>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Badge className={PRIORITY_COLORS[t.priority]}>{PRIORITY_LABELS[t.priority]}</Badge>
                <Badge>{STATUS_LABELS[t.status]}</Badge>
                {t.review_state && (
                  <button type="button" onClick={() => setReviewTask(t)} title="Открыть ревью">
                    <Badge className={REVIEW_STATE_LABELS[t.review_state].className}>
                      <Bot className="mr-1 h-3 w-3" />
                      {REVIEW_STATE_LABELS[t.review_state].label}
                    </Badge>
                  </button>
                )}
                <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                  <Clock className="h-3 w-3" /> {t.estimated_hours}ч
                </span>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              {nextStep(t) && <Button onClick={() => advance(t)}>{nextStep(t)!.label}</Button>}
              {t.review_state && (
                <Button variant="outline" size="sm" onClick={() => setReviewTask(t)}>
                  {t.review_state === "CHANGES_REQUESTED" || t.review_state === "CAPTAIN_REJECTED" ? "Замечания" : "Ревью"}
                </Button>
              )}
            </div>
          </Card>
        ))}
        {open.length === 0 && <Card className="text-center text-slate-500">Открытых задач нет 🎉</Card>}
      </div>

      <ReviewModal task={reviewTask} onClose={() => setReviewTask(null)} onChanged={() => { load(); reload(); }} />

      {done.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm text-slate-600">Выполненные ({done.length})</summary>
          <ul className="mt-2 space-y-1 text-sm text-slate-500">
            {done.map((t) => (
              <li key={t.id} className="line-through">
                {t.title}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: typeof Clock; label: string; value: number }) {
  return (
    <Card className="flex items-center gap-3">
      <Icon className="h-8 w-8 text-indigo-500" />
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-sm text-slate-500">{label}</p>
      </div>
    </Card>
  );
}
