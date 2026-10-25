import { useState, type FormEvent } from "react";
import type { TaskInput, TaskPriority } from "@/api/types";
import { Button, ErrorText, Input, Label, Modal, Select, Textarea } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { PRIORITY_LABELS, SPEC_LABELS } from "@/lib/labels";
import { errorMessage } from "@/lib/utils";

export function TaskFormModal({
  open,
  onClose,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: TaskInput) => Promise<void>;
}) {
  const { project } = useProject();
  const [form, setForm] = useState({ title: "", description: "", assignee_id: "", priority: "MEDIUM" as TaskPriority, estimated_hours: "1" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const assignable = project.members.filter((m) => m.role !== "VIEWER");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSubmit({
        title: form.title,
        description: form.description || null,
        assignee_id: form.assignee_id ? Number(form.assignee_id) : null,
        priority: form.priority,
        estimated_hours: Number(form.estimated_hours) || 1,
      });
      setForm({ title: "", description: "", assignee_id: "", priority: "MEDIUM", estimated_hours: "1" });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="Новая задача" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <Label>Название</Label>
          <Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </div>
        <div>
          <Label>Описание</Label>
          <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <Label>Исполнитель</Label>
            <Select value={form.assignee_id} onChange={(e) => setForm({ ...form, assignee_id: e.target.value })}>
              <option value="">—</option>
              {assignable.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name} ({SPEC_LABELS[m.specialization]})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Приоритет</Label>
            <Select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as TaskPriority })}>
              {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Часы</Label>
            <Input type="number" min="0.5" step="0.5" value={form.estimated_hours} onChange={(e) => setForm({ ...form, estimated_hours: e.target.value })} />
          </div>
        </div>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" className="w-full" disabled={busy}>
          Создать
        </Button>
      </form>
    </Modal>
  );
}
