export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "Что-то пошло не так";
}
