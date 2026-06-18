import type { DiaDemanda } from "../../types";

// ── Indicadores da curva de carga (sobre uma curva 24h em kW) ────────────────
export interface Indicadores {
  dmax: number; dmed: number; dmin: number; e24: number;
  fc: number; fcv: number; hutil: number; fd: number | null;
}

export function indicadores(curva24: number[], dInst: number | null): Indicadores {
  const e24 = curva24.reduce((a, b) => a + b, 0);
  const dmax = Math.max(0, ...curva24);
  const dmin = Math.min(...curva24, dmax);
  const dmed = e24 / 24;
  return {
    e24, dmax, dmin, dmed,
    fc: dmax > 0 ? dmed / dmax : 0,
    fcv: dmax > 0 ? dmin / dmax : 0,
    hutil: dmax > 0 ? e24 / dmax : 0,
    fd: dInst && dInst > 0 ? dmax / dInst : null,
  };
}

// ── P · Q · S por hora (FP informado) ────────────────────────────────────────
export interface PQSHora {
  hora: number; p: number; q: number; s: number;
  fpParcial: number; phi: number; norm: number;
}

/** α de degradação do FP em carga baixa (Starosta/OSE): 0,12 cargas mistas. */
export const ALFA_FP = 0.12;

export function pqsPorHora(curva24: number[], fp: number): PQSHora[] {
  const dmax = Math.max(1e-9, ...curva24);
  const tan = Math.tan(Math.acos(fp));
  return curva24.map((p, h) => {
    const ratio = Math.max(0.01, p / dmax);
    const fpParcial = +(fp * Math.pow(ratio, ALFA_FP)).toFixed(4);
    return {
      hora: h,
      p: +p.toFixed(3),
      q: +(p * tan).toFixed(3),
      s: +(p / fp).toFixed(3),
      fpParcial,
      phi: +(Math.acos(fp) * 180 / Math.PI).toFixed(2),
      norm: +(p / dmax).toFixed(4),
    };
  });
}

// ── Curva de duração (LDC) ───────────────────────────────────────────────────
/** Demanda ordenada decrescente (curva 24h do dia típico). */
export function ldcDiaria(curva24: number[]): number[] {
  return [...curva24].sort((a, b) => b - a);
}

/** Demanda horária do ano inteiro (8.760 h) ordenada decrescente. */
export function ldcAnual(serie: DiaDemanda[]): number[] {
  const todas: number[] = [];
  serie.forEach((d) => { for (let h = 0; h < 24; h++) todas.push(d.perfil_kw[h] ?? 0); });
  return todas.sort((a, b) => b - a);
}

// ── Histograma de frequência (nº de horas por faixa de kW) ───────────────────
export interface Faixa { rotulo: string; cont: number; lo: number; hi: number; }

export function histograma(valores: number[], nFaixas = 10): Faixa[] {
  const max = Math.max(1e-9, ...valores);
  const passo = max / nFaixas;
  return Array.from({ length: nFaixas }, (_, i) => {
    const lo = i * passo, hi = (i + 1) * passo;
    const cont = valores.filter((v) => v >= lo && (i === nFaixas - 1 ? v <= hi : v < hi)).length;
    return { rotulo: `${Math.round(lo)}–${Math.round(hi)}`, cont, lo, hi };
  });
}

/** Curva típica 24h (kW) = média horária sobre todos os dias da série. */
export function curvaTipica(serie: DiaDemanda[]): number[] {
  const soma = Array<number>(24).fill(0);
  serie.forEach((d) => { for (let h = 0; h < 24; h++) soma[h] += d.perfil_kw[h] ?? 0; });
  const n = serie.length || 1;
  return soma.map((s) => +(s / n).toFixed(3));
}
