import { Eye, FileText, GitBranch, Link2, Pencil, Plus, Presentation, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { materialsApi } from "@/api/endpoints";
import type { Material, MaterialType } from "@/api/types";
import { Badge, Button, Card, ErrorText, Input, Label, Modal, Select } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { MATERIAL_LABELS } from "@/lib/labels";
import { errorMessage } from "@/lib/utils";

const ICONS: Record<MaterialType, typeof FileText> = {
  GOOGLE_SLIDES: Presentation,
  GOOGLE_DOCS: FileText,
  FIGMA: Pencil,
  OTHER: Link2,
};

export function MaterialsWidget() {
  const { project, canEdit } = useProject();
  const [materials, setMaterials] = useState<Material[]>([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(
    () => materialsApi.list(project.id).then(setMaterials).catch((e) => setError(errorMessage(e))),
    [project.id],
  );
  useEffect(() => {
    load();
  }, [load]);

  const remove = async (id: number) => {
    await materialsApi.remove(project.id, id);
    load();
  };

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Материалы и ссылки</h2>
        {canEdit && (
          <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" /> Добавить
          </Button>
        )}
      </div>
      <ErrorText>{error}</ErrorText>
      <div className="space-y-2">
        {project.gitlab_repo_url && (
          <a href={project.gitlab_repo_url} target="_blank" rel="noreferrer" className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
            <GitBranch className="h-5 w-5 text-orange-500" />
            <span className="text-sm font-medium">Репозиторий GitLab</span>
          </a>
        )}
        {materials.map((m) => {
          const Icon = ICONS[m.type];
          return (
            <div key={m.id} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3">
              <Icon className="h-5 w-5 shrink-0 text-slate-600" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{m.title}</p>
                <p className="text-xs text-slate-500">{MATERIAL_LABELS[m.type]}</p>
              </div>
              {!m.can_edit && <Badge className="bg-slate-200 text-slate-700">Read-only</Badge>}
              <a href={m.target_url} target="_blank" rel="noreferrer">
                <Button size="sm" variant={m.can_edit ? "default" : "outline"}>
                  {m.can_edit ? <Pencil className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  {m.can_edit ? "Редактировать" : "Только просмотр"}
                </Button>
              </a>
              {m.can_delete && (
                <button onClick={() => remove(m.id)} className="rounded p-1 hover:bg-slate-100" aria-label="Удалить">
                  <Trash2 className="h-4 w-4 text-slate-400" />
                </button>
              )}
            </div>
          );
        })}
        {materials.length === 0 && !project.gitlab_repo_url && <p className="text-sm text-slate-500">Пока пусто</p>}
      </div>
      <AddMaterialModal
        open={adding}
        onClose={() => setAdding(false)}
        onCreated={() => {
          setAdding(false);
          load();
        }}
      />
    </Card>
  );
}

function AddMaterialModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { project } = useProject();
  const [form, setForm] = useState({ title: "", type: "GOOGLE_SLIDES" as MaterialType, edit_url: "", view_url: "" });
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await materialsApi.create(project.id, form);
      setForm({ title: "", type: "GOOGLE_SLIDES", edit_url: "", view_url: "" });
      onCreated();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <Modal open={open} title="Новый материал" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <Label>Название</Label>
          <Input required value={form.title} placeholder="Финальная презентация" onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </div>
        <div>
          <Label>Тип</Label>
          <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as MaterialType })}>
            {Object.entries(MATERIAL_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label>Ссылка для редактирования (Edit URL)</Label>
          <Input required type="url" value={form.edit_url} onChange={(e) => setForm({ ...form, edit_url: e.target.value })} />
        </div>
        <div>
          <Label>Ссылка для просмотра (View URL) — ее увидят наблюдатели</Label>
          <Input required type="url" value={form.view_url} onChange={(e) => setForm({ ...form, view_url: e.target.value })} />
        </div>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" className="w-full">
          Добавить
        </Button>
      </form>
    </Modal>
  );
}
