import { createContext, useContext } from "react";
import type { ProjectDetail, Task } from "@/api/types";

export interface ProjectContextValue {
  project: ProjectDetail;
  reload: () => Promise<void>;
  isCaptain: boolean;
  /** CAPTAIN или MEMBER — может создавать задачи и добавлять материалы */
  canEdit: boolean;
  /** Капитан — любую задачу, участник — только назначенную на него */
  canManageTask: (task: Task) => boolean;
}

export const ProjectContext = createContext<ProjectContextValue | null>(null);

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used inside ProjectLayout");
  return ctx;
}
