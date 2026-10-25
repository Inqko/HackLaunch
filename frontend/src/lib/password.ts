export const PASSWORD_MIN_LENGTH = 8;

const COMMON_PASSWORDS = new Set([
  "password",
  "password1",
  "password123",
  "12345678",
  "123456789",
  "1234567890",
  "qwerty123",
  "qwertyui",
  "qwertyuiop",
  "iloveyou",
  "admin123",
  "welcome1",
  "letmein1",
  "abc12345",
  "passw0rd",
  "hacklaunch",
]);

export interface PasswordRequirement {
  key: string;
  label: string;
  met: boolean;
}

export function passwordRequirements(password: string): PasswordRequirement[] {
  return [
    { key: "length", label: `Минимум ${PASSWORD_MIN_LENGTH} символов`, met: password.length >= PASSWORD_MIN_LENGTH },
    { key: "lower", label: "Строчная буква", met: /[a-z]/.test(password) },
    { key: "upper", label: "Заглавная буква", met: /[A-Z]/.test(password) },
    { key: "digit", label: "Цифра", met: /\d/.test(password) },
    { key: "special", label: "Спецсимвол", met: /[^A-Za-z0-9]/.test(password) },
  ];
}

export function passwordPolicyError(password: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) {
    return `Пароль должен содержать минимум ${PASSWORD_MIN_LENGTH} символов`;
  }
  if (password.length > 128) return "Пароль должен содержать не более 128 символов";
  if (COMMON_PASSWORDS.has(password.toLowerCase())) {
    return "Этот пароль слишком распространён — выберите другой";
  }
  if (!/[a-z]/.test(password)) return "Добавьте хотя бы одну строчную букву";
  if (!/[A-Z]/.test(password)) return "Добавьте хотя бы одну заглавную букву";
  if (!/\d/.test(password)) return "Добавьте хотя бы одну цифру";
  if (!/[^A-Za-z0-9]/.test(password)) {
    return "Добавьте хотя бы один специальный символ (например, !@#$%)";
  }
  if (new Set(password).size < 4) return "Пароль слишком простой — используйте больше разных символов";
  return null;
}

export function passwordStrength(password: string): { score: number; label: string; bar: string; text: string } {
  const met = passwordRequirements(password).filter((r) => r.met).length;
  const score = password ? met : 0;
  if (score >= 5 && !passwordPolicyError(password)) {
    return { score, label: "Надёжный", bar: "bg-emerald-500", text: "text-emerald-700" };
  }
  if (score >= 3) {
    return { score, label: "Средний", bar: "bg-amber-500", text: "text-amber-700" };
  }
  return { score, label: "Слабый", bar: "bg-red-500", text: "text-red-700" };
}
