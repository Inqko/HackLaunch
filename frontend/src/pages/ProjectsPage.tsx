import { GitBranch, Plus, Users } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { projectsApi } from "@/api/endpoints";
import type { ProjectSummary, Specialization } from "@/api/types";
import { Badge, Button, Card, ErrorText, Input, Label, Modal, Progress, Select, Spinner, Textarea } from "@/components/ui";
import { HEALTH_LABELS, ROLE_LABELS, SPEC_LABELS } from "@/lib/labels";
import { errorMessage } from "@/lib/utils";

const CARD_ACCENTS = ["from-indigo-400 to-violet-400", "from-amber-300 to-orange-400", "from-emerald-300 to-teal-400", "from-sky-300 to-blue-400", "from-pink-300 to-rose-400"];

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    projectsApi.list().then(setProjects).catch((e) => setError(errorMessage(e)));
  }, []);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Мои проекты</h1>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> Создать хакатон-проект
        </Button>
      </div>
      <ErrorText>{error}</ErrorText>
      {!projects && !error && <Spinner />}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects?.map((p) => (
          <Link key={p.id} to={`/projects/${p.id}`}>
            <Card className="h-full overflow-hidden p-0 transition hover:-translate-y-0.5 hover:shadow-md">
              <div className={`h-20 bg-gradient-to-r ${CARD_ACCENTS[p.id % CARD_ACCENTS.length]}`} />
              <div className="space-y-3 p-5">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-semibold">{p.name}</h2>
                  <Badge className={HEALTH_LABELS[p.ai_health_status].className}>{HEALTH_LABELS[p.ai_health_status].label}</Badge>
                </div>
                <p className="line-clamp-2 text-sm text-slate-500">{p.description}</p>
                <div>
                  <div className="mb-1 flex justify-between text-xs text-slate-500">
                    <span>Прогресс</span>
                    <span>{p.ai_progress_score}%</span>
                  </div>
                  <Progress value={p.ai_progress_score} />
                </div>
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1">
                    <Users className="h-3.5 w-3.5" /> {p.members_count}
                  </span>
                  {p.gitlab_repo_url && (
                    <span className="inline-flex items-center gap-1">
                      <GitBranch className="h-3.5 w-3.5 text-orange-500" /> GitLab
                    </span>
                  )}
                  <Badge>{ROLE_LABELS[p.my_role]}</Badge>
                </div>
              </div>
            </Card>
          </Link>
        ))}
        {projects?.length === 0 && (
          <Card className="col-span-full text-center text-slate-500">Пока нет проектов — создайте первый!</Card>
        )}
      </div>

      <CreateProjectModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function CreateProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [specialization, setSpecialization] = useState<Specialization>("PM");
  const [autoGitlab, setAutoGitlab] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const project = await projectsApi.create({ name, description, auto_create_gitlab: autoGitlab, specialization });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="Новый хакатон-проект" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label>Название</Label>
          <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="AI Med Assistant" />
        </div>
        <div>
          <Label>Описание идеи (контекст для ИИ)</Label>
          <Textarea
            required
            rows={6}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Какую проблему решаем, для кого, ключевые фичи MVP, стек..."
          />
        </div>
        <div>
          <Label>Моя специализация</Label>
          <Select value={specialization} onChange={(e) => setSpecialization(e.target.value as Specialization)}>
            {Object.entries(SPEC_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoGitlab} onChange={(e) => setAutoGitlab(e.target.checked)} />
          Автоматически создать GitLab-репозиторий
        </label>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Создаем..." : "Создать проект"}
        </Button>
      </form>
    </Modal>
  );
}
