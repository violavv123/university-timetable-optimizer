import axios from "axios";

type ErrorDetail = { loc?: Array<string | number>; msg?: string } | string;

function detailMessage(details: unknown): string {
  if (!details) return "";
  if (typeof details === "string") return details;
  if (Array.isArray(details)) {
    return details
      .map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return "";
        const detail = item as ErrorDetail;
        if (typeof detail === "string") return detail;
        const field = detail.loc?.filter((part) => part !== "body").join(" → ");
        return [field, detail.msg].filter(Boolean).join(": ");
      })
      .filter(Boolean)
      .join(" · ");
  }
  if (typeof details === "object") {
    return Object.entries(details as Record<string, unknown>)
      .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`)
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
