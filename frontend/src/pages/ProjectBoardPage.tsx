import { useCallback, useEffect, useState } from "react";
import { tasksApi } from "@/api/endpoints";
import type { Task } from "@/api/types";
import { AIPulseWidget } from "@/components/project/AIPulseWidget";
import { CaptainApprovalModal } from "@/components/project/CaptainApprovalModal";
import { KanbanBoard } from "@/components/project/KanbanBoard";
import { MaterialsWidget } from "@/components/project/MaterialsWidget";
import { ErrorText } from "@/components/ui";
import { useProject } from "@/context/ProjectContext";
import { errorMessage } from "@/lib/utils";

export default function ProjectBoardPage() {
  const { project, reload, isCaptain } = useProject();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState("");
  const [approvalOpen, setApprovalOpen] = useState(false);

  const loadTasks = useCallback(async () => {
    try {
      setTasks(await tasksApi.list(project.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [project.id]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // После изменения задач обновляем и доску, и процент готовности в шапке AI Pulse
  const onTasksChanged = () => {
    loadTasks();
    reload();
  };

  return (
    <div className="space-y-6">
      <AIPulseWidget onOpenDrafts={() => setApprovalOpen(true)} />
      <ErrorText>{error}</ErrorText>
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <KanbanBoard tasks={tasks} onChange={onTasksChanged} />
        <div className="space-y-4">
          <MaterialsWidget />
        </div>
      </div>
      {isCaptain && <CaptainApprovalModal open={approvalOpen} onClose={() => setApprovalOpen(false)} onApproved={onTasksChanged} />}
    </div>
  );
}
