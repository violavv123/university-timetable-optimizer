import axios from "axios";

type ErrorDetail = { loc?: Array<string | number>; msg?: string } | string;

function detailKey(key: string): string {
  return key.replaceAll("_", " ");
}

function detailMessage(details: unknown): string {
  if (details === null || details === undefined || details === "") return "";
  if (typeof details === "string") return details;
  if (typeof details === "number" || typeof details === "boolean") {
    return String(details);
  }
  if (Array.isArray(details)) {
    return details
      .map((item) => detailMessage(item))
      .filter(Boolean)
      .join(" · ");
  }
  if (typeof details === "object") {
    const value = details as Record<string, unknown>;

    // Scheduling validation responses contain an issue count and a nested
    // array of issue objects. The issue messages are the useful part.
    if (Array.isArray(value.issues)) return detailMessage(value.issues);

    const location = Array.isArray(value.loc)
      ? value.loc.filter((part) => part !== "body").join(" → ")
      : "";
    const message =
      typeof value.message === "string"
        ? value.message
        : typeof value.msg === "string"
          ? value.msg
          : "";
    const code = typeof value.code === "string" ? detailKey(value.code) : "";
    const nested = detailMessage(value.details);

    if (message) {
      const heading = [location, code].filter(Boolean).join(" — ");
      const main = heading ? `${heading}: ${message}` : message;
      return nested ? `${main} (${nested})` : main;
    }

    return Object.entries(value)
      .filter(([key]) => !["issue_count", "loc", "type"].includes(key))
      .map(([key, child]) => {
        const rendered = detailMessage(child);
        return rendered ? `${detailKey(key)}: ${rendered}` : "";
      })
      .filter(Boolean)
      .join(" · ");
  }
  return "";
}

export function getErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Something went wrong. Please try again.";
  if (error.code === "ECONNABORTED") {
    return "The request took longer than expected. Check Run history before trying again because the solver may still be working.";
  }
  if (!error.response) return "Cannot connect to the API. Check that the backend is running.";

  const data = error.response.data as {
    code?: string;
    detail?: ErrorDetail | ErrorDetail[];
    details?: unknown;
    message?: string;
  };
  if (typeof data?.message === "string") {
    const details = detailMessage(data.details);
    return details ? `${data.message} ${details}` : data.message;
  }
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) {
    return detailMessage(data.detail);
  }
  return `Request failed (${error.response.status}).`;
}
