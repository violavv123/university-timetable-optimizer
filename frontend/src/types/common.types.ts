export type Id = number;
export type DayOfWeek = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface MessageResponse {
  message: string;
}

export type EntityRecord = Record<string, unknown> & { id: number };
