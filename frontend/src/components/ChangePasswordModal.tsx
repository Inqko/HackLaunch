import { CheckCircle2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { authApi } from "@/api/endpoints";
import { PasswordStrength } from "@/components/PasswordStrength";
import { Button, ErrorText, Input, Label, Modal, PasswordInput } from "@/components/ui";
import { passwordPolicyError } from "@/lib/password";
import { errorMessage } from "@/lib/utils";

type Step = "form" | "code" | "done";

export function ChangePasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [step, setStep] = useState<Step>("form");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep("form");
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setCode("");
    setMessage("");
    setDebugCode(null);
    setError("");
    setBusy(false);
  }, [open]);

  const requestCode = async () => {
    setError("");
    const policyError = passwordPolicyError(newPassword);
    if (policyError) {
      setError(policyError);
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Пароли не совпадают");
      return;
    }
    setBusy(true);
    try {
      const res = await authApi.requestPasswordChangeCode({ current_password: currentPassword });
      setMessage(res.message);
      setDebugCode(res.debug_code);
      setCode("");
      setStep("code");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const submitForm = async (e: FormEvent) => {
    e.preventDefault();
    await requestCode();
  };

  const submitCode = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!/^\d{6}$/.test(code.trim())) {
      setError("Введите шестизначный код из письма");
      return;
    }
    setBusy(true);
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        code: code.trim(),
      });
      setStep("done");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="Смена пароля" onClose={onClose}>
      {step === "done" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            <CheckCircle2 className="h-4 w-4" /> Пароль изменён
          </div>
          <Button className="w-full" onClick={onClose}>
            Готово
          </Button>
        </div>
      )}

      {step === "form" && (
        <form onSubmit={submitForm} className="space-y-4">
          <div>
            <Label>Текущий пароль</Label>
            <PasswordInput
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </div>
          <div>
            <Label>Новый пароль</Label>
            <PasswordInput
              autoComplete="new-password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <div className="mt-2">
              <PasswordStrength password={newPassword} />
            </div>
          </div>
          <div>
            <Label>Повторите новый пароль</Label>
            <PasswordInput
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>
          <ErrorText>{error}</ErrorText>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Отмена
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Отправляем…" : "Получить код на почту"}
            </Button>
          </div>
        </form>
      )}

      {step === "code" && (
        <form onSubmit={submitCode} className="space-y-4">
          <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {message}
            {debugCode && (
              <p className="mt-1 text-xs text-slate-500">
                Код для демо-режима: <span className="font-mono font-semibold">{debugCode}</span>
              </p>
            )}
          </div>
          <div>
            <Label>Код из письма</Label>
            <Input
              required
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              autoComplete="one-time-code"
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            />
          </div>
          <ErrorText>{error}</ErrorText>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setStep("form");
                setError("");
              }}
              disabled={busy}
            >
              Изменить данные
            </Button>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={requestCode} disabled={busy}>
                Отправить ещё раз
              </Button>
              <Button type="submit" disabled={busy}>
                {busy ? "Проверяем…" : "Сменить пароль"}
              </Button>
            </div>
          </div>
        </form>
      )}
    </Modal>
  );
}
