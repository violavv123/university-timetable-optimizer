import type { AccessTokenResponse, CurrentUser } from "../types";
import { accessToken, httpClient } from "./http-client";

export { accessToken };

export async function signInRequest(
  username: string,
  password: string,
): Promise<string> {
  const body = new URLSearchParams({ username, password });
  const { data } = await httpClient.post<AccessTokenResponse>("/auth/token", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data.access_token;
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const { data } = await httpClient.get<CurrentUser>("/auth/me");
  return data;
}
