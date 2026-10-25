import { Clock, Sparkles } from "lucide-react";
import type { Member, Task } from "@/api/types";
import { Badge } from "@/components/ui";
import { PRIORITY_COLORS, PRIORITY_LABELS, SPEC_LABELS } from "@/lib/labels";

export function TaskCard({ task, assignee, draggable }: { task: Task; assignee?: Member; draggable?: boolean }) {
  return (
    <div
      draggable={draggable}
      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(task.id))}
      className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm data-[draggable=true]:cursor-grab"
      data-draggable={draggable}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="text-sm font-medium">{task.title}</p>
        {task.created_by_ai && <Sparkles className="h-3.5 w-3.5 shrink-0 text-indigo-500" aria-label="Создано ИИ" />}
      </div>
      {/* На карточке — только первый абзац (цель), шаги и критерии видны в личном кабинете */}
      {task.description && <p className="mb-2 line-clamp-2 text-xs text-slate-500">{task.description.split("\n\n")[0]}</p>}
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge className={PRIORITY_COLORS[task.priority]}>{PRIORITY_LABELS[task.priority]}</Badge>
        <span className="inline-flex items-center gap-0.5 text-xs text-slate-500">
          <Clock className="h-3 w-3" /> {task.estimated_hours}ч
        </span>
        {assignee && (
          <Badge className="ml-auto bg-slate-100 text-slate-700">
            {assignee.name} · {SPEC_LABELS[assignee.specialization]}
          </Badge>
        )}
      </div>
    </div>
  );
}
