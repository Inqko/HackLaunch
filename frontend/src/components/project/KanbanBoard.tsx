import { Plus, RefreshCw } from "lucide-react";
import { useState } from "react";
import { gitlabApi, tasksApi } from "@/api/endpoints";
import type { Task, TaskStatus } from "@/api/types";
import { Button, ErrorText } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { BOARD_COLUMNS, STATUS_LABELS } from "@/lib/labels";
import { cn, errorMessage } from "@/lib/utils";
import { ReviewModal } from "./ReviewModal";
import { TaskCard } from "./TaskCard";
import { TaskFormModal } from "./TaskFormModal";

export function KanbanBoard({ tasks, onChange }: { tasks: Task[]; onChange: () => void }) {
  const { project, isCaptain, canEdit, canManageTask } = useProject();
  const [over, setOver] = useState<TaskStatus | null>(null);
  const [adding, setAdding] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [reviewTask, setReviewTask] = useState<Task | null>(null);
  const members = new Map(project.members.map((m) => [m.user_id, m]));

  const moveTo = async (taskId: number, status: TaskStatus) => {
    const task = tasks.find((t) => t.id === taskId);
    if (!task || task.status === status || !canManageTask(task)) return;
    try {
      await tasksApi.update(taskId, { status });
      onChange();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const remove = async (task: Task) => {
    if (!confirm(`Удалить задачу «${task.title}»?`)) return;
    setError("");
    try {
      await tasksApi.remove(task.id);
      onChange();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const syncGitlab = async () => {
    setSyncing(true);
    setError("");
    setNotice("");
    try {
      const result = await gitlabApi.sync(project.id);
      setNotice(
        `GitLab: создано задач ${result.tasks_created}, обновлено ${result.tasks_updated}, приглашено участников ${result.members_invited}.`,
      );
      onChange();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Доска задач</h2>
        {canEdit && (
          <div className="flex items-center gap-2">
            {isCaptain && project.gitlab_repo_url && (
              <Button size="sm" variant="outline" onClick={syncGitlab} disabled={syncing}>
                <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} /> GitLab
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> Задача
            </Button>
          </div>
        )}
      </div>
      <ErrorText>{error}</ErrorText>
      {notice && <p className="mb-3 text-xs text-emerald-700">{notice}</p>}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {BOARD_COLUMNS.map((status) => {
          const column = tasks.filter((t) => t.status === status);
          return (
            <div
              key={status}
              onDragOver={(e) => {
                if (!canEdit) return;
                e.preventDefault();
                setOver(status);
              }}
              onDragLeave={() => setOver(null)}
              onDrop={(e) => {
                setOver(null);
                moveTo(Number(e.dataTransfer.getData("text/plain")), status);
              }}
              className={cn("min-h-[200px] rounded-xl bg-slate-100 p-3 transition", over === status && "ring-2 ring-indigo-400")}
            >
              <div className="mb-3 flex items-center justify-between text-sm font-medium text-slate-600">
                {STATUS_LABELS[status]}
                <span className="rounded-full bg-white px-2 text-xs">{column.length}</span>
              </div>
              <div className="space-y-2">
                {column.map((t) => (
                  <TaskCard
                    key={t.id}
                    task={t}
                    assignee={t.assignee_id ? members.get(t.assignee_id) : undefined}
                    draggable={canManageTask(t)}
                    onDelete={isCaptain ? () => remove(t) : undefined}
                    onOpenReview={() => setReviewTask(t)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <ReviewModal task={reviewTask} onClose={() => setReviewTask(null)} onChanged={onChange} />

      <TaskFormModal
        open={adding}
        onClose={() => setAdding(false)}
        onSubmit={async (data) => {
          await tasksApi.create(project.id, data);
          setAdding(false);
          onChange();
        }}
      />
    </div>
  );
}
