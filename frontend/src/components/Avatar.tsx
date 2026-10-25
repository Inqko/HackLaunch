import { useState } from "react";
import { apiUrl } from "@/api/client";
import { cn } from "@/lib/utils";

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/** Аватар пользователя: картинка, если avatar_url задан, иначе плитка с инициалами. */
export function Avatar({
  src,
  name,
  className = "h-8 w-8 text-xs",
}: {
  src?: string | null;
  name: string;
  className?: string;
}) {
  // Запоминаем, какой именно src не загрузился, чтобы новый аватар снова попробовал отрисоваться
  const [brokenSrc, setBrokenSrc] = useState<string | null>(null);

  if (!src || brokenSrc === src) {
    return (
      <span
        className={cn(
          "inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 font-semibold text-white",
          className,
        )}
      >
        {initials(name) || "?"}
      </span>
    );
  }
  return (
    <img
      src={apiUrl(src)}
      alt={`Аватар ${name}`}
      onError={() => setBrokenSrc(src)}
      loading="lazy"
      className={cn("shrink-0 rounded-full object-cover", className)}
    />
  );
}
