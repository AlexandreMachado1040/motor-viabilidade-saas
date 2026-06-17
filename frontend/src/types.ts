export interface Usuario {
  id: number;
  email: string;
  name: string | null;
  picture: string | null;
  provider: string;
  is_active: boolean;
  is_admin: boolean;
}

export interface AdminUser {
  id: number;
  email: string;
  name: string | null;
  provider: string;
  is_active: boolean;
  is_admin: boolean;
  modulos: ModuloFlags;
}

export type Provedor = "google" | "microsoft";

export type ModuloFlags = Record<string, boolean>;

export interface MeResponse {
  usuario: Usuario;
  modulos: ModuloFlags;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ── MOD 1 — InputLoad ────────────────────────────────────────────────────────
export interface InputLoadPayload {
  demanda_maxima_kw: number | null;
  demanda_kw: number[][]; // 12 × 24
  energia_ponta_kwh: number[]; // 12
  energia_fp_kwh: number[]; // 12
}

export interface LoadResumo {
  valido: boolean;
  erros: string[];
  demanda_maxima_kw: number;
  energia_ponta_total: number;
  energia_fp_total: number;
  energia_total: number;
  energia_equivalente_kwh: number[];
  pico_mensal_kw: number[];
}
