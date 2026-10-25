import { Plus } from "lucide-react";
import { useState } from "react";
import { tasksApi } from "@/api/endpoints";
import type { Task, TaskStatus } from "@/api/types";
import { Button, ErrorText } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { BOARD_COLUMNS, STATUS_LABELS } from "@/lib/labels";
import { cn, errorMessage } from "@/lib/utils";
import { TaskCard } from "./TaskCard";
import { TaskFormModal } from "./TaskFormModal";

export function KanbanBoard({ tasks, onChange }: { tasks: Task[]; onChange: () => void }) {
  const { project, canEdit } = useProject();
  const [over, setOver] = useState<TaskStatus | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const members = new Map(project.members.map((m) => [m.user_id, m]));

  const moveTo = async (taskId: number, status: TaskStatus) => {
    const task = tasks.find((t) => t.id === taskId);
    if (!task || task.status === status) return;
    try {
      await tasksApi.update(taskId, { status });
      onChange();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Доска задач</h2>
        {canEdit && (
          <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" /> Задача
          </Button>
        )}
      </div>
      <ErrorText>{error}</ErrorText>
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
                  <TaskCard key={t.id} task={t} assignee={t.assignee_id ? members.get(t.assignee_id) : undefined} draggable={canEdit} />
                ))}
              </div>
            </div>
          );
        })}
      </div>

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
