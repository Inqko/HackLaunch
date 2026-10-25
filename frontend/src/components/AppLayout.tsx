import { KeyRound, LogOut, Rocket } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { ChangePasswordModal } from "./ChangePasswordModal";
import { Button, Spinner } from "./ui";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const [passwordOpen, setPasswordOpen] = useState(false);
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
          <Link to="/projects" className="flex items-center gap-2 font-semibold">
            <Rocket className="h-5 w-5 text-indigo-600" />
            HackLaunch AI
          </Link>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-600 sm:inline">{user?.name}</span>
            <Button variant="ghost" size="sm" onClick={() => setPasswordOpen(true)} title="Сменить пароль">
              <KeyRound className="h-4 w-4" />
              <span className="hidden sm:inline">Пароль</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut className="h-4 w-4" /> Выйти
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
      <ChangePasswordModal open={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </div>
  );
}
