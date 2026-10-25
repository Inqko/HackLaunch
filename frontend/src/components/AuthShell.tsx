import { Rocket } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "./ui";

export function AuthShell({ title, children, footer }: { title: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-violet-50 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2 text-xl font-bold">
          <Rocket className="h-6 w-6 text-indigo-600" /> HackLaunch AI
        </div>
        <Card>
          <h1 className="mb-4 text-lg font-semibold">{title}</h1>
          {children}
        </Card>
        <p className="mt-4 text-center text-sm text-slate-600">{footer}</p>
      </div>
    </div>
  );
}
