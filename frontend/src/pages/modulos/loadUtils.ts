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

/**
 * Converte texto colado de planilha (12 linhas × 24 colunas) em matriz.
 * Aceita separação por tab, ponto e vírgula ou espaços; decimal pt-BR.
 */
export function parseMatrizColada(texto: string): number[][] {
  const linhas = texto
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  const matriz = matrizZerada();
  linhas.slice(0, 12).forEach((linha, i) => {
    let celulas = linha.split(/[\t;]/);
    if (celulas.length < 2) celulas = linha.split(/\s+/);
    celulas.slice(0, 24).forEach((c, j) => {
      matriz[i][j] = parseNumeroBR(c);
    });
  });
  return matriz;
}

export const fmt = (v: number, dec = 0): string =>
  v.toLocaleString("pt-BR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
