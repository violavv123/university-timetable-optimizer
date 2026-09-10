import axios from "axios";

let currentAccessToken: string | null = null;

export const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export const httpClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 90_000,
});

export const accessToken = {
  get: () => currentAccessToken,
  set: (token: string) => {
    currentAccessToken = token;
  },
  clear: () => {
    currentAccessToken = null;
  },
};

httpClient.interceptors.request.use((config) => {
  const token = accessToken.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !error.config?.url?.includes("/auth/token")
    ) {
      accessToken.clear();
      window.dispatchEvent(new Event("auth:expired"));
    }
    return Promise.reject(error);
  },
);
