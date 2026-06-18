// Tema compartilhado dos gráficos do MOD 1 (paleta exata do Aurova).
export const C = {
  bg: "#0d1530",
  // Fundo do quadro do gráfico: azul translúcido (aparência clean sobre o painel).
  painel: "rgba(23,42,82,0.28)",
  grid: "#94a3b833",
  linha: "#10b981",
  area0: "rgba(16,185,129,0.40)",
  area1: "rgba(16,185,129,0)",
  media: "#f59e0b",
  cursor: "#00c8ff",
  pico: "#ef4444",
  ponta: "#00c8ff",
  foraPonta: "#10b981",
  txt: "#e2e8f0",
  muted: "#94a3b8",
};

/** Arredonda para cima até um número "redondo" (1/2/2,5/5/10 × 10ⁿ). */
export function niceCeil(v: number): number {
  if (v <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(v)));
  const f = v / exp;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * exp;
}
