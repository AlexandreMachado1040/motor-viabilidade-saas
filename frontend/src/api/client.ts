import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { TokenResponse } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// `withCredentials` é essencial: o refresh token trafega em cookie httpOnly.
export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

// O access token vive apenas em memória (não em localStorage) por segurança.
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// Renova o access token via cookie de refresh.
export async function refreshAccessToken(): Promise<string | null> {
  try {
    const { data } = await api.post<TokenResponse>("/auth/refresh");
    setAccessToken(data.access_token);
    return data.access_token;
  } catch {
    setAccessToken(null);
    return null;
  }
}

// Em 401, tenta um único refresh e repete a requisição original.
let refreshing: Promise<string | null> | null = null;

api.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const isRefreshCall = original?.url?.includes("/auth/refresh");

    if (error.response?.status === 401 && original && !original._retry && !isRefreshCall) {
      original._retry = true;
      refreshing = refreshing ?? refreshAccessToken();
      const token = await refreshing;
      refreshing = null;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  },
);
