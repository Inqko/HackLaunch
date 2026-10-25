import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { AuthShell } from "@/components/AuthShell";
import { PasswordResetModal } from "@/components/PasswordResetModal";
import { Button, ErrorText, Input, Label, PasswordInput } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { errorMessage } from "@/lib/utils";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/projects";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [forgotOpen, setForgotOpen] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={from} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <AuthShell title="Вход" footer={<>Нет аккаунта? <Link to="/register" className="font-medium text-indigo-600">Зарегистрироваться</Link></>}>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label>Email</Label>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <Label>Пароль</Label>
            <PasswordInput
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="-mt-2 flex justify-end">
            <button
              type="button"
              onClick={() => setForgotOpen(true)}
              className="text-xs font-medium text-indigo-600 hover:underline"
            >
              Забыли пароль?
            </button>
          </div>
          <ErrorText>{error}</ErrorText>
          <Button type="submit" className="w-full" disabled={busy}>
            Войти
          </Button>
        </form>
      </AuthShell>
      <PasswordResetModal open={forgotOpen} onClose={() => setForgotOpen(false)} initialEmail={email} />
    </>
  );
}
