import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { analyticsApi } from "@/api/endpoints";
import type { Analytics } from "@/api/types";
import { Button, Card, ErrorText, Progress, Spinner } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { ROLE_LABELS, SPEC_LABELS } from "@/lib/labels";
import { errorMessage } from "@/lib/utils";

export default function AnalyticsPage() {
  const { project } = useProject();
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    analyticsApi.get(project.id).then(setData).catch((e) => setError(errorMessage(e)));
  }, [project.id]);

  const download = (format: "csv" | "json") =>
    analyticsApi.export(project.id, format).catch((e) => setError(errorMessage(e)));

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!data) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Вклад команды</h2>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => download("csv")}>
            <Download className="h-4 w-4" /> Скачать CSV
          </Button>
          <Button variant="outline" onClick={() => download("json")}>
            <Download className="h-4 w-4" /> JSON
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Всего задач" value={data.total_tasks} />
        <StatCard label="Выполнено" value={data.completed_tasks} />
        <StatCard label="Коммитов в GitLab" value={data.total_commits} />
        <StatCard label="Merge Requests" value={data.total_mrs} />
      </div>

      <Card>
        <h3 className="mb-4 font-medium">Задачи и коммиты по участникам</h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.members_stats}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" fontSize={12} />
              <YAxis fontSize={12} allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Bar dataKey="tasks_completed" name="Задач закрыто" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="hours_completed" name="Часов закрыто" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="gitlab_commits" name="Коммиты" fill="#f97316" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="border-b bg-slate-50 text-left text-slate-500">
            <tr>
              {["Участник", "Задачи", "В работе", "Готово", "Часы", "Коммиты", "MR", "Вклад"].map((h) => (
                <th key={h} className="px-4 py-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.members_stats.map((m) => (
              <tr key={m.user_id} className="border-b last:border-0">
                <td className="px-4 py-3">
                  <p className="font-medium">{m.name}</p>
                  <p className="text-xs text-slate-500">
                    {ROLE_LABELS[m.role]} · {SPEC_LABELS[m.specialization]}
                  </p>
                </td>
                <td className="px-4 py-3">{m.tasks_assigned}</td>
                <td className="px-4 py-3">{m.tasks_in_progress}</td>
                <td className="px-4 py-3">{m.tasks_completed}</td>
                <td className="px-4 py-3">{m.hours_completed}</td>
                <td className="px-4 py-3">{m.gitlab_commits}</td>
                <td className="px-4 py-3">{m.gitlab_mrs}</td>
                <td className="w-40 px-4 py-3">
                  <div className="mb-1 text-xs font-medium">{m.contribution_percent}%</div>
                  <Progress value={m.contribution_percent} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <p className="text-3xl font-bold">{value}</p>
      <p className="text-sm text-slate-500">{label}</p>
    </Card>
  );
}
