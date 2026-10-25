import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout, RequireAuth } from "./components/AppLayout";
import ProjectLayout from "./components/ProjectLayout";
import AnalyticsPage from "./pages/AnalyticsPage";
import CabinetPage from "./pages/CabinetPage";
import LoginPage from "./pages/LoginPage";
import MyWorkspacePage from "./pages/MyWorkspacePage";
import ProjectBoardPage from "./pages/ProjectBoardPage";
import ProjectsPage from "./pages/ProjectsPage";
import RegisterPage from "./pages/RegisterPage";
import TeamPage from "./pages/TeamPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/cabinet" element={<CabinetPage />} />
        <Route path="/projects/:id" element={<ProjectLayout />}>
          <Route index element={<ProjectBoardPage />} />
          <Route path="my-workspace" element={<MyWorkspacePage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}
