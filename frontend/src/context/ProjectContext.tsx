import { createContext, useContext } from "react";
import type { ProjectDetail } from "@/api/types";

export interface ProjectContextValue {
  project: ProjectDetail;
  reload: () => Promise<void>;
  isCaptain: boolean;
  /** CAPTAIN или MEMBER — может создавать/двигать задачи и добавлять материалы */
  canEdit: boolean;
}

export const ProjectContext = createContext<ProjectContextValue | null>(null);

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used inside ProjectLayout");
  return ctx;
}
