const API_URL = import.meta.env.VITE_API_URL ?? "";
const TOKEN_KEY = "hl_token";

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* приватный режим — токен живет до перезагрузки */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* noop */
    }
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Абсолютный URL для ресурсов бэкенда (картинки и т.п.), когда фронт и API на разных origin */
export function apiUrl(path: string): string {
  return path.startsWith("/") ? `${API_URL}${path}` : path;
}

async function request(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  const isForm = body instanceof FormData;
  // Для FormData Content-Type с boundary выставит сам браузер
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) tokenStore.clear();
  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = await res.json();
      message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(res.status, message);
  }
  return res;
}

async function json<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await request(method, path, body);
  return res.status === 204 ? (undefined as T) : res.json();
}

export const http = {
  get: <T>(path: string) => json<T>("GET", path),
  post: <T>(path: string, body?: unknown) => json<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => json<T>("PATCH", path, body),
  put: <T>(path: string, body: unknown) => json<T>("PUT", path, body),
  del: <T = void>(path: string) => json<T>("DELETE", path),
  upload: <T>(path: string, form: FormData) => json<T>("POST", path, form),

  /** Скачивает файл с бэкенда, сохраняя имя из Content-Disposition */
  async download(path: string, fallbackName: string) {
    const res = await request("GET", path);
    const disposition = res.headers.get("Content-Disposition") ?? "";
    const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? fallbackName;
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  },
};
