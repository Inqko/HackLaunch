import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { passwordRequirements, passwordStrength } from "@/lib/password";

export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  const requirements = passwordRequirements(password);
  const strength = passwordStrength(password);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="flex h-1.5 flex-1 gap-1">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className={cn(
                "h-full flex-1 rounded-full transition-colors",
                i < strength.score ? strength.bar : "bg-slate-200",
              )}
            />
          ))}
        </div>
        <span className={cn("text-xs font-medium", strength.text)}>{strength.label}</span>
      </div>
      <ul className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
        {requirements.map((requirement) => (
          <li
            key={requirement.key}
            className={cn(
              "flex items-center gap-1 text-xs",
              requirement.met ? "text-emerald-700" : "text-slate-500",
            )}
          >
            {requirement.met ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
            {requirement.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
