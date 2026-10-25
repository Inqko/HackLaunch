import { AlertTriangle, ClipboardCheck, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { aiApi } from "@/api/endpoints";
import { Badge, Button, Card, ErrorText, Modal, Progress, Textarea } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { HEALTH_LABELS } from "@/lib/labels";
import { errorMessage } from "@/lib/utils";

export function AIPulseWidget({ onOpenDrafts }: { onOpenDrafts: () => void }) {
  const { project, reload, isCaptain, canEdit } = useProject();
  const [busy, setBusy] = useState<"refresh" | "generate" | null>(null);
  const [error, setError] = useState("");
  const [genNotice, setGenNotice] = useState<{ text: string; warn: boolean } | null>(null);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [context, setContext] = useState("");
  const health = HEALTH_LABELS[project.ai_health_status];

  const refresh = async () => {
    setBusy("refresh");
    setError("");
    try {
      await aiApi.refreshStatus(project.id);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const generate = async () => {
    setBusy("generate");
    setError("");
    setGenNotice(null);
    try {
      const res = await aiApi.generateTasks(project.id, context || undefined);
      setGenNotice(
        res.warning
          ? { text: res.warning, warn: true }
          : { text: `Сгенерировано ${res.tasks.length} задач (${res.model ?? "ИИ"}).`, warn: false },
      );
      setGenerateOpen(false);
      setContext("");
      onOpenDrafts();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="border-indigo-200 bg-gradient-to-br from-indigo-50 to-white">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-600" />
            <h2 className="font-semibold">AI Pulse — состояние проекта</h2>
            <Badge className={health.className}>{health.label}</Badge>
          </div>
          <div className="max-w-md">
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-slate-600">Готовность</span>
              <span className="font-semibold">{project.ai_progress_score}%</span>
            </div>
            <Progress value={project.ai_progress_score} />
          </div>
          <p className="text-sm text-slate-700">
            {project.ai_health_summary ?? "ИИ еще не анализировал проект. Нажмите «Обновить анализ»."}
          </p>
          {project.ai_risks.length > 0 && (
            <ul className="space-y-1">
              {project.ai_risks.map((risk) => (
                <li key={risk} className="flex items-start gap-2 text-sm text-amber-800">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {risk}
                </li>
              ))}
            </ul>
          )}
          <ErrorText>{error}</ErrorText>
          {genNotice && (
            <p className={genNotice.warn ? "rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" : "text-xs text-slate-500"}>
              {genNotice.text}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-2">
          {isCaptain && (
            <>
              <Button variant="ai" onClick={() => setGenerateOpen(true)} disabled={busy !== null}>
                <Sparkles className="h-4 w-4" /> Сгенерировать задачи через ИИ
              </Button>
              <Button variant="outline" onClick={onOpenDrafts}>
                <ClipboardCheck className="h-4 w-4" /> Черновики на утверждение
              </Button>
            </>
          )}
          {canEdit && (
            <Button variant="outline" onClick={refresh} disabled={busy !== null}>
              <RefreshCw className={`h-4 w-4 ${busy === "refresh" ? "animate-spin" : ""}`} /> Обновить анализ
            </Button>
          )}
        </div>
      </div>

      <Modal open={generateOpen} title="Сформировать план задач с ИИ" onClose={() => setGenerateOpen(false)}>
        <p className="mb-3 text-sm text-slate-600">
          ИИ учтет описание проекта и специализации участников. Можно добавить уточнение — например, конкретную фичу.
        </p>
        <Textarea
          rows={4}
          value={context}
          onChange={(e) => setContext(e.target.value)}
          placeholder="Дополнительный контекст (необязательно)"
        />
        <Button variant="ai" className="mt-4 w-full" onClick={generate} disabled={busy !== null}>
          {busy === "generate" ? "ИИ продумывает проект и пишет задачи (до 2 минут)..." : "Сгенерировать"}
        </Button>
      </Modal>
    </Card>
  );
}
