import { Plus, Sparkles, Trash2, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";
import { tasksApi } from "@/api/endpoints";
import type { Task, TaskPriority } from "@/api/types";
import { Button, ErrorText, Input, Modal, Select, Spinner, Textarea } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { PRIORITY_LABELS, SPEC_LABELS } from "@/lib/labels";
import { cn, errorMessage } from "@/lib/utils";

interface DraftRow {
  key: string;
  id: number | null; // null — задача, добавленная Капитаном вручную
  title: string;
  description: string;
  assignee_id: number | null;
  priority: TaskPriority;
  estimated_hours: number;
  removed: boolean;
}

const toRow = (t: Task): DraftRow => ({
  key: `d${t.id}`,
  id: t.id,
  title: t.title,
  description: t.description ?? "",
  assignee_id: t.assignee_id,
  priority: t.priority,
  estimated_hours: t.estimated_hours,
  removed: false,
});

export function CaptainApprovalModal({ open, onClose, onApproved }: { open: boolean; onClose: () => void; onApproved: () => void }) {
  const { project } = useProject();
  const [rows, setRows] = useState<DraftRow[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const assignable = project.members.filter((m) => m.role !== "VIEWER");

  useEffect(() => {
    if (!open) return;
    setRows(null);
    setError("");
    tasksApi
      .drafts(project.id)
      .then((groups) => setRows(groups.flatMap((g) => g.tasks.map(toRow))))
      .catch((e) => setError(errorMessage(e)));
  }, [open, project.id]);

  const patch = (key: string, changes: Partial<DraftRow>) =>
    setRows((rs) => rs?.map((r) => (r.key === key ? { ...r, ...changes } : r)) ?? null);

  const addRow = (assignee_id: number | null) =>
    setRows((rs) => [
      ...(rs ?? []),
      { key: `n${Date.now()}`, id: null, title: "", description: "", assignee_id, priority: "MEDIUM", estimated_hours: 1, removed: false },
    ]);

  const approve = async () => {
    if (!rows) return;
    setBusy(true);
    setError("");
    try {
      const kept = rows.filter((r) => !r.removed && r.title.trim());
      await tasksApi.approveBatch(project.id, {
        approved_tasks: kept.map(({ id, title, description, assignee_id, priority, estimated_hours }) => ({
          id,
          title,
          description: description || null,
          assignee_id,
          priority,
          estimated_hours,
        })),
        rejected_task_ids: rows.filter((r) => r.removed && r.id !== null).map((r) => r.id!),
      });
      onApproved();
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  // Группировка по текущему исполнителю — переназначение сразу «переносит» задачу в другую группу
  const groups = [...assignable.map((m) => ({ id: m.user_id as number | null, title: `${m.name} · ${SPEC_LABELS[m.specialization]}` })), { id: null, title: "Без исполнителя" }];
  const activeCount = rows?.filter((r) => !r.removed).length ?? 0;

  return (
    <Modal open={open} title="Утверждение задач от ИИ" onClose={onClose} wide>
      {!rows && !error && <Spinner />}
      {rows && rows.length === 0 && (
        <p className="py-6 text-center text-slate-500">
          Черновиков нет. Нажмите «Сгенерировать задачи через ИИ» на главном экране.
        </p>
      )}
      {rows && rows.length > 0 && (
        <div className="max-h-[60vh] space-y-5 overflow-y-auto pr-1">
          {groups.map((g) => {
            const groupRows = rows.filter((r) => r.assignee_id === g.id);
            if (g.id === null && groupRows.length === 0) return null;
            return (
              <section key={g.id ?? "none"}>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="font-medium">{g.title}</h3>
                  <Button size="sm" variant="ghost" onClick={() => addRow(g.id)}>
                    <Plus className="h-4 w-4" /> Добавить
                  </Button>
                </div>
                <div className="space-y-2">
                  {groupRows.map((r) => (
                    <div key={r.key} className={cn("rounded-lg border p-3", r.removed ? "border-dashed opacity-50" : "border-slate-200")}>
                      <div className="flex gap-2">
                        {r.id !== null && <Sparkles className="mt-2.5 h-4 w-4 shrink-0 text-indigo-500" />}
                        <Input value={r.title} disabled={r.removed} placeholder="Название задачи" onChange={(e) => patch(r.key, { title: e.target.value })} />
                        <Button variant="ghost" size="sm" className="mt-1" onClick={() => patch(r.key, { removed: !r.removed })} aria-label={r.removed ? "Вернуть" : "Удалить"}>
                          {r.removed ? <Undo2 className="h-4 w-4" /> : <Trash2 className="h-4 w-4 text-red-600" />}
                        </Button>
                      </div>
                      {!r.removed && (
                        <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_180px_140px_90px] sm:items-start">
                          <Textarea className="min-h-[40px] text-xs" rows={6} value={r.description} placeholder="Описание, шаги, критерии готовности" onChange={(e) => patch(r.key, { description: e.target.value })} />
                          <Select value={r.assignee_id ?? ""} onChange={(e) => patch(r.key, { assignee_id: e.target.value ? Number(e.target.value) : null })}>
                            <option value="">Без исполнителя</option>
                            {assignable.map((m) => (
                              <option key={m.user_id} value={m.user_id}>
                                {m.name}
                              </option>
                            ))}
                          </Select>
                          <Select value={r.priority} onChange={(e) => patch(r.key, { priority: e.target.value as TaskPriority })}>
                            {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
                              <option key={v} value={v}>
                                {l}
                              </option>
                            ))}
                          </Select>
                          <Input type="number" min="0.5" step="0.5" value={r.estimated_hours} onChange={(e) => patch(r.key, { estimated_hours: Number(e.target.value) || 1 })} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
      <ErrorText>{error}</ErrorText>
      {rows && rows.length > 0 && (
        <div className="mt-4 flex items-center justify-between border-t pt-4">
          <span className="text-sm text-slate-500">К утверждению: {activeCount}</span>
          <Button onClick={approve} disabled={busy}>
            {busy ? "Сохраняем..." : "Утвердить и разослать по личным кабинетам"}
          </Button>
        </div>
      )}
    </Modal>
  );
}
