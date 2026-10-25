import { Trash2, UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { projectsApi } from "@/api/endpoints";
import type { ProjectRole, Specialization } from "@/api/types";
import { Avatar } from "@/components/Avatar";
import { Badge, Button, Card, ErrorText, Input, Label, Select } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useProject } from "@/context/ProjectContext";
import { ROLE_LABELS, SPEC_LABELS } from "@/lib/labels";
import { errorMessage } from "@/lib/utils";

function Options({ labels }: { labels: Record<string, string> }) {
  return (
    <>
      {Object.entries(labels).map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </>
  );
}

export default function TeamPage() {
  const { project, reload, isCaptain } = useProject();
  const { user } = useAuth();
  const [error, setError] = useState("");

  const run = async (action: () => Promise<unknown>) => {
    setError("");
    try {
      await action();
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <div className="space-y-6">
      {isCaptain && <InviteForm onInvite={(data) => run(() => projectsApi.addMember(project.id, data))} />}
      <ErrorText>{error}</ErrorText>
      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="border-b bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Участник</th>
              <th className="px-4 py-3 font-medium">GitLab</th>
              <th className="px-4 py-3 font-medium">Роль</th>
              <th className="px-4 py-3 font-medium">Специализация</th>
              {isCaptain && <th />}
            </tr>
          </thead>
          <tbody>
            {project.members.map((m) => {
              const editable = isCaptain && m.user_id !== user?.id;
              return (
                <tr key={m.user_id} className="border-b last:border-0">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar src={m.avatar_url} name={m.name} className="h-8 w-8 text-xs" />
                      <div>
                        <p className="font-medium">{m.name}</p>
                        <p className="text-xs text-slate-500">{m.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{m.gitlab_username ?? "—"}</td>
                  <td className="px-4 py-3">
                    {editable ? (
                      <Select
                        className="w-40"
                        value={m.role}
                        onChange={(e) => run(() => projectsApi.updateMember(project.id, m.user_id, { role: e.target.value as ProjectRole }))}
                      >
                        <Options labels={ROLE_LABELS} />
                      </Select>
                    ) : (
                      <Badge>{ROLE_LABELS[m.role]}</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {isCaptain ? (
                      <Select
                        className="w-40"
                        value={m.specialization}
                        onChange={(e) =>
                          run(() => projectsApi.updateMember(project.id, m.user_id, { specialization: e.target.value as Specialization }))
                        }
                      >
                        <Options labels={SPEC_LABELS} />
                      </Select>
                    ) : (
                      SPEC_LABELS[m.specialization]
                    )}
                  </td>
                  {isCaptain && (
                    <td className="px-4 py-3 text-right">
                      {editable && (
                        <button
                          onClick={() => confirm(`Удалить ${m.name} из проекта?`) && run(() => projectsApi.removeMember(project.id, m.user_id))}
                          className="rounded p-1 hover:bg-slate-100"
                          aria-label="Удалить"
                        >
                          <Trash2 className="h-4 w-4 text-slate-400" />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function InviteForm({ onInvite }: { onInvite: (data: { email: string; role: ProjectRole; specialization: Specialization }) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ProjectRole>("MEMBER");
  const [specialization, setSpecialization] = useState<Specialization>("BACKEND");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await onInvite({ email, role, specialization });
    setEmail("");
  };

  return (
    <Card>
      <h2 className="mb-3 font-semibold">Пригласить участника</h2>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-[1fr_160px_160px_auto] sm:items-end">
        <div>
          <Label>Email зарегистрированного пользователя</Label>
          <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <Label>Роль</Label>
          <Select value={role} onChange={(e) => setRole(e.target.value as ProjectRole)}>
            <Options labels={ROLE_LABELS} />
          </Select>
        </div>
        <div>
          <Label>Специализация</Label>
          <Select value={specialization} onChange={(e) => setSpecialization(e.target.value as Specialization)}>
            <Options labels={SPEC_LABELS} />
          </Select>
        </div>
        <Button type="submit">
          <UserPlus className="h-4 w-4" /> Добавить
        </Button>
      </form>
    </Card>
  );
}
