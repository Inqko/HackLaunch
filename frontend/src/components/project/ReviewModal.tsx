import { Bot, ExternalLink, GitMerge, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { reviewApi } from "@/api/endpoints";
import type { Task, TaskReviews } from "@/api/types";
import { Badge, Button, ErrorText, Modal, Spinner, Textarea } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { REVIEW_STATE_LABELS, REVIEW_VERDICT_LABELS } from "@/lib/labels";
import { errorMessage } from "@/lib/utils";

/** История ИИ-ревью задачи и решение капитана (влить MR / отклонить) */
export function ReviewModal({ task, onClose, onChanged }: { task: Task | null; onClose: () => void; onChanged: () => void }) {
  const { isCaptain } = useProject();
  const [data, setData] = useState<TaskReviews | null>(null);
  const [comment, setComment] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!task) return;
    try {
      setData(await reviewApi.list(task.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [task]);

  useEffect(() => {
    setData(null);
    setError("");
    setComment("");
    setRejecting(false);
    load();
  }, [load]);

  // Пока ИИ проверяет — обновляем окно
  useEffect(() => {
    if (data?.task.review_state !== "AI_REVIEWING") return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [data?.task.review_state, load]);

  const act = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await action();
      onChanged();
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const current = data?.task;
  const state = current?.review_state ? REVIEW_STATE_LABELS[current.review_state] : null;
  const awaitingCaptain = isCaptain && current?.review_state === "AWAITING_CAPTAIN";

  return (
    <Modal open={task !== null} title={task ? `Ревью: ${task.title}` : ""} onClose={onClose} wide>
      {!data && !error && <Spinner />}
      {current && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {state && <Badge className={state.className}>{state.label}</Badge>}
            {current.branch_name && <code className="rounded bg-slate-100 px-2 py-0.5 text-xs">{current.branch_name}</code>}
            {data.mr_url && (
              <a href={data.mr_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-indigo-600 hover:underline">
                <GitMerge className="h-4 w-4" /> Merge Request <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>

          {current.review_state === "AI_REVIEWING" && (
            <p className="flex items-center gap-2 rounded-md bg-violet-50 px-3 py-2 text-sm text-violet-700">
              <Spinner /> ИИ проверяет изменения в ветке — обычно это занимает до минуты.
            </p>
          )}

          <div className="max-h-[50vh] space-y-3 overflow-y-auto pr-1">
            {data.reviews.map((r) => {
              const v = REVIEW_VERDICT_LABELS[r.verdict] ?? { label: r.verdict, className: "bg-slate-100 text-slate-700" };
              return (
                <div key={r.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    {r.reviewer === "AI" ? <Bot className="h-4 w-4 text-violet-600" /> : <UserRound className="h-4 w-4 text-sky-600" />}
                    <Badge className={v.className}>{v.label}</Badge>
                    <span>{new Date(r.created_at).toLocaleString("ru-RU")}</span>
                    {r.commit_sha && <code>{r.commit_sha.slice(0, 8)}</code>}
                  </div>
                  <p className="whitespace-pre-line text-sm">{r.summary}</p>
                  {r.issues.length > 0 && (
                    <ul className="mt-2 space-y-1 text-sm">
                      {r.issues.map((i, idx) => (
                        <li key={idx} className="rounded bg-amber-50 px-2 py-1 text-amber-900">
                          {i.file && (
                            <code className="mr-1 text-xs">
                              {i.file}
                              {i.line ? `:${i.line}` : ""}
                            </code>
                          )}
                          {i.comment}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
            {data.reviews.length === 0 && current.review_state !== "AI_REVIEWING" && (
              <p className="text-sm text-slate-500">Ревью еще не было.</p>
            )}
          </div>

          {awaitingCaptain && (
            <div className="space-y-2 border-t pt-4">
              {rejecting ? (
                <>
                  <Textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Что нужно исправить?" />
                  <div className="flex gap-2">
                    <Button variant="destructive" disabled={busy || !comment.trim()} onClick={() => act(() => reviewApi.reject(current.id, comment))}>
                      Вернуть в работу
                    </Button>
                    <Button variant="ghost" onClick={() => setRejecting(false)}>
                      Отмена
                    </Button>
                  </div>
                </>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <Button disabled={busy} onClick={() => act(() => reviewApi.approve(current.id))}>
                    <GitMerge className="h-4 w-4" /> {busy ? "Вливаем..." : "Влить MR и закрыть задачу"}
                  </Button>
                  <Button variant="outline" disabled={busy} onClick={() => setRejecting(true)}>
                    Отклонить
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      <ErrorText>{error}</ErrorText>
    </Modal>
  );
}
