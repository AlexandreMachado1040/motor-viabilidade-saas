import { api } from "./client";
import { DEMO_MODE } from "../config";
import { EXEMPLO_LOAD, validarLoadLocal } from "../pages/modulos/loadDemo";
import type {
  InputLoadPayload, LoadResumo, PayloadModulo, SimuladorTarifasPayload, SimuladorTarifasResumo,
  SummaryPayload, SummaryResumo,
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

// ── MOD 2 — Simulador de modalidades tarifárias ─────────────────────────────
// Cálculo só no motor Python (sem versão no navegador), como o summary.
export function getExemploTarifas(): Promise<SimuladorTarifasPayload> {
  return api.get<SimuladorTarifasPayload>("/modulos/grid/exemplo-tarifas").then((r) => r.data);
}

export function simularTarifas(payload: SimuladorTarifasPayload): Promise<SimuladorTarifasResumo> {
  return api.post<SimuladorTarifasResumo>("/modulos/grid/simular-tarifas", payload).then((r) => r.data);
}

// ── MOD 3/4/9 — Investimentos e parâmetros financeiros ──────────────────────
export type ModuloInvestimento = "solar" | "bess_ponta" | "cf";

export function validarModulo(modulo: ModuloInvestimento, payload: PayloadModulo): Promise<PayloadModulo> {
  return api.post<PayloadModulo>(`/modulos/${modulo}/validar`, payload).then((r) => r.data);
}
