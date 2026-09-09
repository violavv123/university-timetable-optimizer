import type { DayOfWeek, TimetableRunStatus } from "../types";

export const DAY_NAMES: Record<DayOfWeek, string> = {
  1: "Monday",
  2: "Tuesday",
  3: "Wednesday",
  4: "Thursday",
  5: "Friday",
  6: "Saturday",
  7: "Sunday",
};

export const WORK_DAYS: DayOfWeek[] = [1, 2, 3, 4, 5];

export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function shortTime(value: string | undefined): string {
  return value?.slice(0, 5) ?? "—";
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function formatDuration(milliseconds: number | null): string {
  if (milliseconds === null) return "—";
  return milliseconds < 1000 ? `${milliseconds} ms` : `${(milliseconds / 1000).toFixed(1)} s`;
}

export function statusTone(status: TimetableRunStatus): "success" | "warning" | "danger" | "neutral" {
  if (status === "SUCCEEDED") return "success";
  if (status === "RUNNING" || status === "PENDING") return "warning";
  if (status === "FAILED" || status === "INFEASIBLE") return "danger";
  return "neutral";
}
