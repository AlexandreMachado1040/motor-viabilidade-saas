import { api } from "./client";
import { DEMO_MODE } from "../config";
import { EXEMPLO_LOAD, validarLoadLocal } from "../pages/modulos/loadDemo";
import type {
  InputLoadPayload, LoadResumo, PayloadModulo, SummaryPayload, SummaryResumo,
} from "../types";

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

// ── Dados de referência dos módulos (planilha original do motor) ─────────────
export type ModuloComExemplo = "grid" | "solar" | "bess_ponta" | "cf";

export function getExemploModulo(modulo: ModuloComExemplo): Promise<PayloadModulo> {
  return api.get<PayloadModulo>(`/modulos/${modulo}/exemplo`).then((r) => r.data);
}

// ── MOD 10 — Summary ─────────────────────────────────────────────────────────
// Sem versão no navegador: o estudo completo (8 módulos + fluxo de caixa) só
// existe no motor Python. No modo demo a página mostra aviso em vez de chamar.
export function calcularEstudo(payload: SummaryPayload): Promise<SummaryResumo> {
  return api.post<SummaryResumo>("/modulos/summary/validar", payload).then((r) => r.data);
}
