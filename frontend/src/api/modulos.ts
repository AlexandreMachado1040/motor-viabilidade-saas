import { api } from "./client";
import { DEMO_MODE } from "../config";
import { EXEMPLO_LOAD, validarLoadLocal } from "../pages/modulos/loadDemo";
import type { InputLoadPayload, LoadResumo } from "../types";

// ── MOD 1 — InputLoad ────────────────────────────────────────────────────────
// No modo demo, roda 100% no navegador (sem backend).
export function getExemploLoad(): Promise<InputLoadPayload> {
  if (DEMO_MODE) return Promise.resolve(EXEMPLO_LOAD);
  return api.get<InputLoadPayload>("/modulos/load/exemplo").then((r) => r.data);
}

export function validarLoad(payload: InputLoadPayload): Promise<LoadResumo> {
  if (DEMO_MODE) return Promise.resolve(validarLoadLocal(payload));
  return api.post<LoadResumo>("/modulos/load/validar", payload).then((r) => r.data);
}
