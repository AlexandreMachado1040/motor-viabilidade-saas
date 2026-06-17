import { api } from "./client";
import type { InputLoadPayload, LoadResumo } from "../types";

// ── MOD 1 — InputLoad ────────────────────────────────────────────────────────
export function getExemploLoad(): Promise<InputLoadPayload> {
  return api.get<InputLoadPayload>("/modulos/load/exemplo").then((r) => r.data);
}

export function validarLoad(payload: InputLoadPayload): Promise<LoadResumo> {
  return api.post<LoadResumo>("/modulos/load/validar", payload).then((r) => r.data);
}
