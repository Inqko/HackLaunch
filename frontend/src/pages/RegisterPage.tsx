import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { AuthShell } from "@/components/AuthShell";
import { PasswordStrength } from "@/components/PasswordStrength";
import { Button, ErrorText, Input, Label, PasswordInput } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { passwordPolicyError } from "@/lib/password";
import { errorMessage } from "@/lib/utils";

export default function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", gitlab_username: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/projects" replace />;

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    const policyError = passwordPolicyError(form.password);
    if (policyError) {
      setError(policyError);
      return;
    }
    setBusy(true);
    try {
      await register({ ...form, gitlab_username: form.gitlab_username || undefined });
      navigate("/projects", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Регистрация" footer={<>Уже есть аккаунт? <Link to="/login" className="font-medium text-indigo-600">Войти</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label>Имя</Label>
          <Input required value={form.name} onChange={set("name")} />
        </div>
        <div>
          <Label>Email</Label>
          <Input type="email" required value={form.email} onChange={set("email")} />
        </div>
        <div>
          <Label>Пароль</Label>
          <PasswordInput
            autoComplete="new-password"
            required
            value={form.password}
            onChange={set("password")}
          />
          <div className="mt-2">
            <PasswordStrength password={form.password} />
          </div>
        </div>
        <div>
          <Label>GitLab username (необязательно)</Label>
          <Input placeholder="для инвайта в репозиторий и статистики" value={form.gitlab_username} onChange={set("gitlab_username")} />
        </div>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" className="w-full" disabled={busy}>
          Создать аккаунт
        </Button>
      </form>
    </AuthShell>
  );
}
