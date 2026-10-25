import { useCallback, useEffect, useState } from "react";

// Ключи привязаны к пользователю: иначе на общем компьютере второй аккаунт
// продолжал чужой таймер и видел чужое время
const activeKey = (userId: number | undefined) => `hl_cabinet_timer_v2:${userId ?? "anon"}`;
const logKey = (userId: number | undefined) => `hl_cabinet_time_log_v2:${userId ?? "anon"}`;

export interface ActiveTimer {
  taskId: number;
  title: string;
  projectName: string;
  startedAt: number;
}

interface DayLog {
  total: number;
  byTask: Record<string, number>;
}

type TimeLog = Record<string, DayLog>;

function todayKey(date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function readActive(key: string): ActiveTimer | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ActiveTimer>;
    if (typeof parsed.taskId !== "number" || typeof parsed.startedAt !== "number") return null;
    return {
      taskId: parsed.taskId,
      title: parsed.title ?? `Задача #${parsed.taskId}`,
      projectName: parsed.projectName ?? "",
      startedAt: parsed.startedAt,
    };
  } catch {
    return null;
  }
}

function readLog(key: string): TimeLog {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as TimeLog;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

/** Режет интервал по полуночи, чтобы ночная сессия не записалась целиком в «сегодня» */
function splitByDay(startMs: number, endMs: number): [string, number][] {
  const parts: [string, number][] = [];
  let cursor = startMs;
  while (cursor < endMs) {
    const day = new Date(cursor);
    const nextMidnight = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1).getTime();
    const until = Math.min(endMs, nextMidnight);
    parts.push([todayKey(day), Math.floor((until - cursor) / 1000)]);
    cursor = until;
  }
  return parts;
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* приватный режим — таймер живет до перезагрузки */
  }
}

/**
 * Локальный таймер работы над задачей.
 * Состояние и накопленное время хранятся в localStorage, поэтому переживают
 * перезагрузку страницы. Сервер о времени не знает — это личная статистика.
 */
export function useWorkTimer(userId: number | undefined) {
  const ACTIVE_KEY = activeKey(userId);
  const LOG_KEY = logKey(userId);
  const [active, setActive] = useState<ActiveTimer | null>(() => readActive(ACTIVE_KEY));
  const [log, setLog] = useState<TimeLog>(() => readLog(LOG_KEY));
  const [now, setNow] = useState(() => Date.now());
  const [loadedKey, setLoadedKey] = useState(LOG_KEY);

  // Сменился пользователь — подгружаем его таймер, а не пишем свой лог под чужим ключом
  if (loadedKey !== LOG_KEY) {
    setLoadedKey(LOG_KEY);
    setActive(readActive(ACTIVE_KEY));
    setLog(readLog(LOG_KEY));
  }

  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);

  useEffect(() => {
    if (loadedKey === LOG_KEY) write(LOG_KEY, log);
  }, [log, loadedKey, LOG_KEY]);

  const addInterval = useCallback((timer: ActiveTimer, endMs: number) => {
    const parts = splitByDay(timer.startedAt, endMs).filter(([, seconds]) => seconds > 0);
    if (parts.length === 0) return;
    setLog((prev) => {
      const next = { ...prev };
      for (const [day, seconds] of parts) {
        const current = next[day] ?? { total: 0, byTask: {} };
        next[day] = {
          total: current.total + seconds,
          byTask: { ...current.byTask, [timer.taskId]: (current.byTask[timer.taskId] ?? 0) + seconds },
        };
      }
      return next;
    });
  }, []);

  const stop = useCallback(() => {
    if (!active) return;
    addInterval(active, Date.now());
    setActive(null);
    try {
      localStorage.removeItem(ACTIVE_KEY);
    } catch {
      /* noop */
    }
  }, [active, addInterval, ACTIVE_KEY]);

  const start = useCallback(
    (taskId: number, meta: { title: string; projectName: string }) => {
      if (active?.taskId === taskId) return;
      if (active) stop();
      const next: ActiveTimer = { taskId, title: meta.title, projectName: meta.projectName, startedAt: Date.now() };
      setActive(next);
      write(ACTIVE_KEY, next);
      setNow(Date.now());
    },
    [active, stop, ACTIVE_KEY],
  );

  const toggle = useCallback(
    (taskId: number, meta: { title: string; projectName: string }) => {
      if (active?.taskId === taskId) stop();
      else start(taskId, meta);
    },
    [active, start, stop],
  );

  const activeSeconds = active ? Math.max(0, Math.floor((now - active.startedAt) / 1000)) : 0;
  const today = log[todayKey()] ?? { total: 0, byTask: {} };
  // В «сегодня» идёт только часть активной сессии после полуночи
  const activeToday = active ? (splitByDay(active.startedAt, now).find(([day]) => day === todayKey())?.[1] ?? 0) : 0;

  const todayTotal = today.total + activeToday;
  const secondsForTask = (taskId: number) =>
    (today.byTask[taskId] ?? 0) + (active?.taskId === taskId ? activeToday : 0);

  return { active, activeSeconds, todayTotal, secondsForTask, start, stop, toggle };
}

export function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

export function formatTracked(totalSeconds: number): string {
  const minutes = Math.floor(Math.max(0, totalSeconds) / 60);
  if (minutes < 60) return `${minutes} мин`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} ч ${m} мин` : `${h} ч`;
}
