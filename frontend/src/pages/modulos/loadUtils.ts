export const MESES = [
  "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
  "Jul", "Ago", "Set", "Out", "Nov", "Dez",
];

export const HORAS = Array.from({ length: 24 }, (_, h) => h);

export function matrizZerada(): number[][] {
  return Array.from({ length: 12 }, () => Array<number>(24).fill(0));
}

export function vetorZerado(): number[] {
  return Array<number>(12).fill(0);
}

/** Normaliza número no padrão pt-BR (1.234,56 → 1234.56). */
export function parseNumeroBR(token: string): number {
  let s = token.trim();
  if (!s) return 0;
  if (s.includes(".") && s.includes(",")) s = s.replace(/\./g, "").replace(",", ".");
  else if (s.includes(",")) s = s.replace(",", ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

export const fmt = (v: number, dec = 0): string =>
  v.toLocaleString("pt-BR", { minimumFractionDigits: dec, maximumFractionDigits: dec });

// Dias por mês (ano bissexto de referência → eixo de até 366 dias).
export const DIAS_MES = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

/** Dia do ano (1-366) para um par mês/dia, usando referência bissexta. */
export function diaDoAno(mes: number, dia: number): number {
  let d = dia;
  for (let m = 0; m < mes - 1; m++) d += DIAS_MES[m];
  return d;
}

/** Início (dia do ano) de cada mês — para faixas/rótulos do eixo X. */
export const INICIO_MES = MESES.map((_, i) => diaDoAno(i + 1, 1));

/**
 * Gera uma série diária representativa a partir da demanda mensal/horária: cada
 * dia do mês recebe o perfil médio daquele mês. Usado quando não há leituras brutas
 * (exemplo/demo, ou entrada manual) — apenas para visualização.
 */
export function serieDiariaDeMatriz(matriz: number[][]): import("../../types").DiaDemanda[] {
  const serie: import("../../types").DiaDemanda[] = [];
  for (let m = 0; m < 12; m++) {
    const perfil = matriz[m] ?? Array<number>(24).fill(0);
    const total = perfil.reduce((a, b) => a + b, 0); // kW horário ⇒ kWh/dia
    const pico = Math.max(0, ...perfil);
    for (let dia = 1; dia <= DIAS_MES[m]; dia++) {
      serie.push({
        ano: 0, mes: m + 1, dia, doy: diaDoAno(m + 1, dia),
        total_kwh: +total.toFixed(2), pico_kw: +pico.toFixed(2),
        perfil_kw: perfil.slice(0, 24),
      });
    }
  }
  return serie;
}

