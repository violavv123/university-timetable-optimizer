import type { Paginated } from "../types";
import { httpClient } from "./http-client";

export type QueryParameters = Record<
  string,
  string | number | boolean | undefined | null
>;

export async function fetchPage<T>(
  path: string,
  params: QueryParameters = {},
): Promise<Paginated<T>> {
  const { data } = await httpClient.get<Paginated<T>>(path, { params });
  return data;
}

export async function fetchAll<T>(
  path: string,
  params: QueryParameters = {},
): Promise<T[]> {
  const first = await fetchPage<T>(path, { ...params, page: 1, page_size: 100 });
  if (first.total_pages <= 1) return first.items;

  const remaining = await Promise.all(
    Array.from({ length: first.total_pages - 1 }, (_, index) =>
      fetchPage<T>(path, { ...params, page: index + 2, page_size: 100 }),
    ),
  );
  return [first, ...remaining].flatMap((page) => page.items);
}
