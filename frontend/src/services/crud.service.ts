import type { MessageResponse } from "../types";
import { httpClient } from "./http-client";

export const crudService = {
  create: async <T>(path: string, payload: Record<string, unknown>) =>
    (await httpClient.post<T>(path, payload)).data,
  update: async <T>(path: string, id: number, payload: Record<string, unknown>) =>
    (await httpClient.patch<T>(`${path}/${id}`, payload)).data,
  remove: async (path: string, id: number) =>
    (await httpClient.delete<MessageResponse>(`${path}/${id}`)).data,
};
