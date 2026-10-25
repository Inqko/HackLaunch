import { useCallback, useEffect, useState } from "react";

const ACTIVE_KEY = "hl_cabinet_timer_v1";
const LOG_KEY = "hl_cabinet_time_log_v1";

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

function readActive(): ActiveTimer | null {
  try {
    const raw = localStorage.getItem(ACTIVE_KEY);
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

function readLog(): TimeLog {
  try {
    const raw = localStorage.getItem(LOG_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as TimeLog;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
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
export function useWorkTimer() {
  const [active, setActive] = useState<ActiveTimer | null>(readActive);
  const [log, setLog] = useState<TimeLog>(readLog);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);

  useEffect(() => {
    write(LOG_KEY, log);
  }, [log]);

  const addSeconds = useCallback((timer: ActiveTimer, seconds: number) => {
    if (seconds <= 0) return;
    setLog((prev) => {
      const day = todayKey();
      const current = prev[day] ?? { total: 0, byTask: {} };
      return {
        ...prev,
        [day]: {
          total: current.total + seconds,
          byTask: { ...current.byTask, [timer.taskId]: (current.byTask[timer.taskId] ?? 0) + seconds },
        },
      };
    });
  }, []);

  const stop = useCallback(() => {
    if (!active) return;
    addSeconds(active, Math.floor((Date.now() - active.startedAt) / 1000));
    setActive(null);
    try {
      localStorage.removeItem(ACTIVE_KEY);
    } catch {
      /* noop */
    }
  }, [active, addSeconds]);

  const start = useCallback(
    (taskId: number, meta: { title: string; projectName: string }) => {
      if (active?.taskId === taskId) return;
      if (active) stop();
      const next: ActiveTimer = { taskId, title: meta.title, projectName: meta.projectName, startedAt: Date.now() };
      setActive(next);
      write(ACTIVE_KEY, next);
      setNow(Date.now());
    },
    [active, stop],
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

  const todayTotal = today.total + activeSeconds;
  const secondsForTask = (taskId: number) =>
    (today.byTask[taskId] ?? 0) + (active?.taskId === taskId ? activeSeconds : 0);

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
