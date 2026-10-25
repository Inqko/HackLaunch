import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { projectsApi } from "@/api/endpoints";
import type { ProjectDetail } from "@/api/types";
import { Button, ErrorText, Input, Label, Modal } from "@/components/ui";
import { errorMessage } from "@/lib/utils";

export function DeleteProjectModal({ project, open, onClose }: { project: ProjectDetail; open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [confirmName, setConfirmName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Удаление необратимо, поэтому просим ввести название, а не просто нажать «ОК»
  const matches = confirmName.trim() === project.name.trim();

  const close = () => {
    if (busy) return;
    setConfirmName("");
    setError("");
    onClose();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!matches) return;
    setBusy(true);
    setError("");
    try {
      await projectsApi.remove(project.id);
      navigate("/projects", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="Удалить проект" onClose={close}>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-slate-600">
          Будут удалены все задачи, материалы и участники проекта <b>{project.name}</b>. Это действие нельзя отменить.
          {project.gitlab_repo_url && " Репозиторий в GitLab останется — удалите его там вручную, если он больше не нужен."}
        </p>
        <div>
          <Label>Введите название проекта для подтверждения</Label>
          <Input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} placeholder={project.name} autoFocus />
        </div>
        <ErrorText>{error}</ErrorText>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={close} disabled={busy}>
            Отмена
          </Button>
          <Button type="submit" variant="destructive" disabled={!matches || busy}>
            {busy ? "Удаляем..." : "Удалить проект"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
