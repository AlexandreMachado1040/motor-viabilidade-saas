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
  demanda_kw: number[][]; // [mês][hora] em kW
  energia_ponta_kwh: number[]; // 12
  energia_fp_kwh: number[]; // 12
}

// Demanda máxima de cada mês por posto (kW), medida no intervalo do arquivo.
// Só existe para memória de massa real — curva-tipo não tem pico de fatura.
export interface PicosMensais {
  demanda_ponta_kw: (number | null)[]; // 12; null = mês sem leitura
  demanda_fp_kw: (number | null)[]; // 12
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

// ── MOD 10 — Summary (estudo de viabilidade completo) ────────────────────────
// Os payloads dos módulos de referência (grid, solar, bess_ponta, cf) passam
// adiante sem edição nesta tela — o backend valida cada um pelo schema do
// próprio módulo, então aqui ficam opacos.
export type PayloadModulo = Record<string, unknown>;

export interface SummaryPayload {
  load: InputLoadPayload;
  grid: PayloadModulo;
  params_cf?: PayloadModulo;
  solar?: PayloadModulo | null;
  bess_ponta?: PayloadModulo | null;
}

export interface SummaryResumo {
  valido: boolean;
  erros: string[];
  projeto: {
    concessionaria: string | null;
    subgrupo: string | null;
    demanda_maxima_kw: number | null;
    potencia_solar_kwp: number | null;
    energia_bess_kwh: number | null;
  };
  custos: {
    opex_grid_anual: number | null;
    capex_total: number | null;
  };
  indicadores: {
    vpl: number | null;
    tir_pct: number | null;
    payback: number | null;
    roi: number | null;
    viavel: boolean | null;
  };
  modulos_ativos: Record<string, boolean>;
}

/** Fator de potência extraído da memória de massa (colunas de reativa). */
export interface FPInfo {
  pPorHora: number[];    // 24 — potência ativa média (kW) por hora
  qPorHora: number[];    // 24 — potência reativa média (kVAr) por hora
  fpPorHora: number[];   // 24 — FP por hora
  capPorHora: boolean[]; // 24 — hora com reativo capacitivo predominante
  medio: number;         // FP médio global
  ponta: number;         // FP médio na ponta
  fora: number;          // FP médio fora-ponta
  fonte: string;         // origem (demanda kVAr / consumo kVArh)
}

/** Um dia real da memória de massa, para a análise diária ao longo do ano. */
export interface DiaDemanda {
  ano: number;
  mes: number; // 1-12
  dia: number; // 1-31
  doy: number; // dia do ano (1-366, ref. bissexto)
  total_kwh: number;
  pico_kw: number;
  perfil_kw: number[]; // 24 — kW médio por hora
}

// ── MOD 2 — Simulador de modalidades tarifárias ─────────────────────────────
export interface TarifasConvencional { demanda: number; consumo: number }
export interface TarifasAzul {
  demanda_ponta: number; demanda_fp: number; consumo_ponta: number; consumo_fp: number;
  consumo_ponta_umido?: number | null; consumo_fp_umido?: number | null;
}
export interface TarifasVerde {
  demanda: number; consumo_ponta: number; consumo_fp: number;
  consumo_ponta_umido?: number | null; consumo_fp_umido?: number | null;
}
export interface TarifasBaixaTensao { consumo: number }

export interface SimuladorTarifasPayload {
  demanda_ponta_kw: number[];
  demanda_fp_kw: number[];
  consumo_ponta_kwh: number[];
  consumo_fp_kwh: number[];
  demanda_contratada_kw: number;
  demanda_contratada_ponta_kw: number;
  demanda_contratada_fp_kw: number;
  tolerancia_ultrapassagem: number;
  fator_ultrapassagem: number;
  convencional: TarifasConvencional | null;
  azul: TarifasAzul | null;
  verde: TarifasVerde | null;
  baixa_tensao: TarifasBaixaTensao | null;
}

export interface ModalidadeResultado {
  modalidade: string;
  custo_anual: number;
  custo_mensal: number[];
  componentes: Record<string, number>;
  ultrapassagem_anual: number;
  meses_com_ultrapassagem: number;
}

export interface DemandaSugerida {
  modalidade: string;
  demanda_kw: number | null;
  demanda_ponta_kw: number | null;
  demanda_fp_kw: number | null;
  custo_anual: number;
  economia_anual: number;
}

export interface SimuladorTarifasResumo {
  valido: boolean;
  erros: string[];
  modalidades: ModalidadeResultado[];
  recomendada: string | null;
  economia_vs_atual: Record<string, number>;
  demandas_sugeridas: DemandaSugerida[];
}
