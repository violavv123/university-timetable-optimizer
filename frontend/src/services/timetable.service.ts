import type {
  GenerationRequest,
  MessageResponse,
  TimetableEntry,
  TimetableRun,
  ValidationResult,
} from "../types";
import { httpClient } from "./http-client";

export const timetableService = {
  generate: async (payload: GenerationRequest) =>
    (
      await httpClient.post<TimetableRun>("/timetables/generate", payload, {
        timeout: 0,
      })
    ).data,
  validate: async (runId: number) =>
    (await httpClient.get<ValidationResult>(`/timetables/runs/${runId}/validation`)).data,
  publish: async (runId: number) =>
    (await httpClient.post<TimetableRun>(`/timetables/runs/${runId}/publish`)).data,
  unpublish: async (runId: number) =>
    (await httpClient.post<TimetableRun>(`/timetables/runs/${runId}/unpublish`)).data,
  cancel: async (runId: number) =>
    (await httpClient.post<TimetableRun>(`/timetables/runs/${runId}/cancel`)).data,
  lockEntry: async (entryId: number, isLocked: boolean) =>
    (await httpClient.patch<TimetableEntry>(`/timetables/entries/${entryId}/lock`, { is_locked: isLocked })).data,
  validateOffering: async (offeringId: number) =>
    (await httpClient.post<MessageResponse>(`/scheduling-input/course-offerings/${offeringId}/validate-readiness`)).data,
  reoptimize: async (sourceRunId: number, payload: GenerationRequest) => {
    const prepared = await httpClient.post<TimetableRun>(
      `/timetables/runs/${sourceRunId}/reoptimized-run`,
      { ...payload, source_type: "REOPTIMIZED" },
    );
    return (
      await httpClient.post<TimetableRun>(
        `/timetables/runs/${prepared.data.id}/generate`,
      )
    ).data;
  },
  downloadCsv: async (run: TimetableRun) => {
    const { data } = await httpClient.get<Blob>(
      `/timetables/runs/${run.id}/download`,
      { responseType: "blob" },
    );
    const url = URL.createObjectURL(data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${run.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },
};
