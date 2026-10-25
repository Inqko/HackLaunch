import { Bot, Clock, Sparkles, Trash2 } from "lucide-react";
import type { Member, Task } from "@/api/types";
import { Badge } from "@/components/ui";
import { PRIORITY_COLORS, PRIORITY_LABELS, REVIEW_STATE_LABELS, SPEC_LABELS } from "@/lib/labels";

export function TaskCard({
  task,
  assignee,
  draggable,
  onDelete,
  onOpenReview,
}: {
  task: Task;
  assignee?: Member;
  draggable?: boolean;
  onDelete?: () => void;
  onOpenReview?: () => void;
}) {
  const review = task.review_state ? REVIEW_STATE_LABELS[task.review_state] : null;
  return (
    <div
      draggable={draggable}
      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(task.id))}
      className="group rounded-lg border border-slate-200 bg-white p-3 shadow-sm data-[draggable=true]:cursor-grab"
      data-draggable={draggable}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="text-sm font-medium">{task.title}</p>
        <div className="flex shrink-0 items-center gap-1">
          {task.created_by_ai && <Sparkles className="h-3.5 w-3.5 text-indigo-500" aria-label="Создано ИИ" />}
          {onDelete && (
            // На тач-экранах hover нет, поэтому кнопка скрывается только на широких экранах
            <button
              type="button"
              onClick={onDelete}
              className="rounded p-0.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600 focus:opacity-100 md:opacity-0 md:group-hover:opacity-100"
              aria-label="Удалить задачу"
              title="Удалить задачу"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
      {/* На карточке — только первый абзац (цель), шаги и критерии видны в личном кабинете */}
      {task.description && <p className="mb-2 line-clamp-2 text-xs text-slate-500">{task.description.split("\n\n")[0]}</p>}
      {review && (
        <button
          type="button"
          onClick={onOpenReview}
          className="mb-2 inline-flex items-center gap-1 rounded-full text-left hover:opacity-80"
          title="Открыть ревью"
        >
          <Badge className={review.className}>
            <Bot className="mr-1 h-3 w-3" />
            {review.label}
          </Badge>
        </button>
      )}
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
