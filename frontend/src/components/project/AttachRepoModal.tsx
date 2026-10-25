import { ExternalLink } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { gitlabApi } from "@/api/endpoints";
import { Button, ErrorText, Input, Label, Modal } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { errorMessage } from "@/lib/utils";

/** Капитан сам создает репозиторий на gitlab.com и прикрепляет его ссылкой */
export function AttachRepoModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { project, reload } = useProject();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setUrl(project.gitlab_repo_url ?? "");
    setError("");
    setWarning("");
  }, [open, project.gitlab_repo_url]);

  const run = async (action: () => Promise<string | null | undefined>) => {
    setBusy(true);
    setError("");
    try {
      const warn = await action();
      await reload();
      if (warn) setWarning(warn);
      else onClose();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(async () => (await gitlabApi.attach(project.id, url)).warning);
  };

  return (
    <Modal open={open} title="GitLab-репозиторий проекта" onClose={onClose}>
      <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm text-slate-600">
        <li>
          Создайте репозиторий на{" "}
          <a href="https://gitlab.com/projects/new" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-indigo-600 hover:underline">
            gitlab.com <ExternalLink className="h-3 w-3" />
          </a>{" "}
          — лучше в группе команды, чтобы работала синхронизация задач.
        </li>
        <li>Скопируйте ссылку на него и вставьте ниже.</li>
      </ol>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <Label>Ссылка на репозиторий</Label>
          <Input required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://gitlab.com/группа/репозиторий" />
        </div>
        <ErrorText>{error}</ErrorText>
        {warning && (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Ссылка сохранена. {warning}
          </p>
        )}
        <div className="flex gap-2">
          <Button type="submit" className="flex-1" disabled={busy}>
            {busy ? "Сохраняем..." : project.gitlab_repo_url ? "Сохранить" : "Прикрепить"}
          </Button>
          {project.gitlab_repo_url && (
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => run(async () => (await gitlabApi.detach(project.id), null))}
            >
              Открепить
            </Button>
          )}
        </div>
      </form>
    </Modal>
  );
}
