import type { ModuloInvestimento } from "../../api/modulos";
import type { PayloadModulo } from "../../types";

// Telas de solar, BESS de ponta e parâmetros financeiros. Cada uma edita só
// os campos comerciais; o resto do payload vem do exemplo de referência do
// motor (/modulos/<modulo>/exemplo) e é ajustado em `montar`.

export type Unidade = "R$" | "%" | "kW" | "kWp" | "kWh" | "anos" | "ano" | "x";

export interface CampoInvestimento {
  campo: string;
  rotulo: string;
  unidade: Unidade;
  inteiro?: boolean;
  min?: number;
  max?: number;
}

export interface ConfigInvestimento {
  modulo: ModuloInvestimento;
  titulo: string;
  subtitulo: string;
  nota: string;
  campos: CampoInvestimento[];
  /** Payload completo a partir da referência e dos valores digitados (% já em fração). */
  montar: (referencia: PayloadModulo, valores: Record<string, number>) => PayloadModulo;
  /** Linha curta para o resumo do estudo. */
  resumir: (payload: PayloadModulo) => string;
}

const num = (o: PayloadModulo, campo: string): number => {
  const v = o[campo];
  return typeof v === "number" ? v : 0;
};

const escalarMatriz = (m: unknown, fator: number): number[][] =>
  Array.isArray(m) ? (m as number[][]).map((linha) => linha.map((v) => v * fator)) : [];

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const nf = (v: number, d = 0) => v.toLocaleString("pt-BR", { maximumFractionDigits: d });

export const SOLAR: ConfigInvestimento = {
  modulo: "solar",
  titulo: "MOD 3 · Solar",
  subtitulo: "sistema fotovoltaico com compensação (GD)",
  nota: "A geração hora a hora é a do sistema de referência (300 kWp, São Paulo), escalada pela potência "
    + "informada. Serve para explorar porte e CAPEX; para outra localidade o perfil não muda.",
  campos: [
    { campo: "potencia_cc_kwp", rotulo: "Potência instalada", unidade: "kWp", min: 0.1 },
    { campo: "sobrecarga_inversor", rotulo: "Sobrecarga do inversor (CC/CA)", unidade: "x", min: 1 },
    { campo: "capex_r", rotulo: "CAPEX", unidade: "R$", min: 0 },
    { campo: "om_anual_r", rotulo: "O&M anual", unidade: "R$", min: 0 },
    { campo: "degradacao_ano1", rotulo: "Degradação no 1º ano", unidade: "%", min: 0, max: 100 },
    { campo: "degradacao_demais", rotulo: "Degradação dos demais anos", unidade: "%", min: 0, max: 100 },
    { campo: "custo_troca_inversor_r", rotulo: "Troca do inversor", unidade: "R$", min: 0 },
    { campo: "ano_troca_inversor", rotulo: "Ano da troca do inversor", unidade: "ano", inteiro: true, min: 0 },
    { campo: "data_estudo_ano", rotulo: "Ano de início da operação", unidade: "ano", inteiro: true, min: 2000 },
  ],
  montar: (ref, v) => {
    const refKwp = num(ref, "potencia_cc_kwp");
    const fator = refKwp > 0 ? v.potencia_cc_kwp / refKwp : 0;
    return {
      ...ref,
      ...v,
      potencia_ca_kw: v.potencia_cc_kwp / v.sobrecarga_inversor,
      potencia_gerada_kw: escalarMatriz(ref.potencia_gerada_kw, fator),
      potencia_injetada_kw: escalarMatriz(ref.potencia_injetada_kw, fator),
    };
  },
  resumir: (p) => `${nf(num(p, "potencia_cc_kwp"))} kWp · CAPEX ${brl(num(p, "capex_r"))}`,
};

export const BESS_PONTA: ConfigInvestimento = {
  modulo: "bess_ponta",
  titulo: "MOD 4 · BESS de ponta",
  subtitulo: "bateria que abate o consumo no horário de ponta",
  nota: "Energias e tempos de carga/descarga são recalculados a partir da energia útil e das potências. "
    + "Os demais dados técnicos (módulos, tensões, correntes) continuam os do sistema de referência e não "
    + "entram no cálculo.",
  campos: [
    { campo: "capex_r", rotulo: "CAPEX", unidade: "R$", min: 0 },
    { campo: "energia_dod80_pos_pcs", rotulo: "Energia útil (após PCS)", unidade: "kWh", min: 0.1 },
    { campo: "potencia_max_descarga_kw", rotulo: "Potência de descarga", unidade: "kW", min: 0.1 },
    { campo: "potencia_max_carga_kw", rotulo: "Potência de carga", unidade: "kW", min: 0.1 },
    { campo: "eta_total", rotulo: "Eficiência de ciclo", unidade: "%", min: 1, max: 100 },
    { campo: "percentual_eol", rotulo: "Capacidade no fim da vida", unidade: "%", min: 0, max: 100 },
    { campo: "tempo_reposicao_anos", rotulo: "Reposição a cada", unidade: "anos", inteiro: true, min: 1 },
    { campo: "custo_reposicao_r", rotulo: "Custo da reposição", unidade: "R$", min: 0 },
  ],
  montar: (ref, v) => {
    // Mantém as relações da referência: DoD 80% antes do PCS = útil / eficiência do PCS etc.
    const refUtil = num(ref, "energia_dod80_pos_pcs");
    const fator = refUtil > 0 ? v.energia_dod80_pos_pcs / refUtil : 0;
    const dod80 = num(ref, "energia_dod80_kwh") * fator;
    return {
      ...ref,
      ...v,
      vida_util_anos: v.tempo_reposicao_anos,
      energia_dod80_kwh: dod80,
      energia_dod100_kwh: num(ref, "energia_dod100_kwh") * fator,
      energia_dod100_pos_pcs: num(ref, "energia_dod100_pos_pcs") * fator,
      capacidade_c10_ah: num(ref, "capacidade_c10_ah") * fator,
      tempo_carga_h: dod80 / v.potencia_max_carga_kw,
      tempo_descarga_h: dod80 / v.potencia_max_descarga_kw,
    };
  },
  resumir: (p) => `${nf(num(p, "energia_dod80_pos_pcs"), 1)} kWh úteis · CAPEX ${brl(num(p, "capex_r"))}`,
};

export const CF: ConfigInvestimento = {
  modulo: "cf",
  titulo: "MOD 9 · Parâmetros financeiros",
  subtitulo: "taxa de desconto, horizonte e reajustes do fluxo de caixa",
  nota: "Os reajustes corrigem, ano a ano, a tarifa do posto usada no custo da rede e nas economias de "
    + "solar e BESS. A taxa de desconto é nominal.",
  campos: [
    { campo: "taxa_desconto", rotulo: "Taxa de desconto (nominal)", unidade: "%", min: 0, max: 100 },
    { campo: "inflacao", rotulo: "Inflação", unidade: "%", min: 0, max: 100 },
    { campo: "anos_projeto", rotulo: "Horizonte", unidade: "anos", inteiro: true, min: 1, max: 50 },
    { campo: "reajuste_tarifa_ponta", rotulo: "Reajuste da tarifa de ponta", unidade: "%", min: -100, max: 100 },
    { campo: "reajuste_tarifa_fp", rotulo: "Reajuste da tarifa fora ponta", unidade: "%", min: -100, max: 100 },
    { campo: "reajuste_demanda_spt", rotulo: "Reajuste da demanda", unidade: "%", min: -100, max: 100 },
    { campo: "reajuste_combustivel", rotulo: "Reajuste do combustível", unidade: "%", min: -100, max: 100 },
  ],
  montar: (ref, v) => ({ ...ref, ...v }),
  resumir: (p) =>
    `Desconto ${nf(num(p, "taxa_desconto") * 100, 2)}% a.a. · ${nf(num(p, "anos_projeto"))} anos`,
};

export const CONFIGS: Record<ModuloInvestimento, ConfigInvestimento> = {
  solar: SOLAR,
  bess_ponta: BESS_PONTA,
  cf: CF,
};

/** Valores de tela (percentuais em %) a partir de um payload. */
export function valoresDoPayload(cfg: ConfigInvestimento, p: PayloadModulo): Record<string, string> {
  const valores: Record<string, string> = {};
  for (const c of cfg.campos) {
    const v = num(p, c.campo);
    valores[c.campo] = String(c.unidade === "%" ? +(v * 100).toFixed(6) : v);
  }
  return valores;
}

/** Converte a tela em números (% → fração); devolve erros legíveis em vez de valores inválidos. */
export function lerValores(
  cfg: ConfigInvestimento, tela: Record<string, string>,
): { valores?: Record<string, number>; erros: string[] } {
  const erros: string[] = [];
  const valores: Record<string, number> = {};
  for (const c of cfg.campos) {
    const bruto = (tela[c.campo] ?? "").trim().replace(",", ".");
    const v = Number(bruto);
    if (bruto === "" || !Number.isFinite(v)) {
      erros.push(`Informe ${c.rotulo.toLowerCase()}.`);
      continue;
    }
    if (c.inteiro && !Number.isInteger(v)) {
      erros.push(`${c.rotulo} deve ser um número inteiro.`);
      continue;
    }
    if ((c.min !== undefined && v < c.min) || (c.max !== undefined && v > c.max)) {
      const faixa = [c.min !== undefined ? `mínimo ${c.min}` : "", c.max !== undefined ? `máximo ${c.max}` : ""]
        .filter(Boolean).join(", ");
      erros.push(`${c.rotulo}: fora da faixa (${faixa}).`);
      continue;
    }
    valores[c.campo] = c.unidade === "%" ? v / 100 : v;
  }
  return erros.length > 0 ? { erros } : { valores, erros };
}
