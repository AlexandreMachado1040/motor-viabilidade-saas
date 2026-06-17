import type { InputLoadPayload, LoadResumo } from "../../types";

// Dados da planilha original (espelham backend exemplo_load_payload),
// usados no modo demo para o InputLoad funcionar sem backend.
export const EXEMPLO_LOAD: InputLoadPayload = {
  demanda_maxima_kw: 238.56,
  demanda_kw: [
    [16.8,17.64,15.96,16.8,17.64,15.96,15.12,21.0,42.84,51.24,55.44,56.28,63.0,121.8,151.2,151.2,158.76,146.16,123.48,121.8,125.16,33.6,20.16,21.0],
    [36.96,17.64,17.64,16.8,19.32,16.8,21.84,63.84,88.2,95.76,101.64,104.16,140.28,196.56,215.04,215.88,186.48,211.68,111.72,88.2,89.04,77.28,57.96,40.32],
    [19.32,18.48,20.16,20.16,18.48,17.64,40.32,77.28,100.8,105.0,112.56,117.6,151.2,204.12,215.04,225.96,214.2,198.24,133.56,99.12,98.28,92.4,76.44,27.72],
    [15.12,14.28,14.28,13.44,13.44,15.12,21.0,28.56,36.12,72.24,67.2,66.36,94.92,163.8,168.0,152.88,151.2,145.32,73.92,84.0,76.44,63.84,57.12,34.44],
    [16.8,15.96,14.28,15.96,14.28,15.12,18.48,28.56,42.0,46.2,51.24,52.08,63.84,124.32,152.88,143.64,129.36,118.44,78.96,84.0,81.48,61.32,43.68,21.0],
    [17.64,15.96,18.48,16.8,17.64,15.96,21.0,25.2,27.72,29.4,32.76,38.64,48.72,99.96,99.96,93.24,79.8,72.24,36.96,40.32,41.16,36.96,33.6,25.2],
    [13.44,13.44,13.44,13.44,13.44,13.44,17.64,22.68,25.2,26.04,28.56,26.04,37.8,88.2,91.56,79.8,73.92,75.6,25.2,26.88,26.04,25.2,20.16,15.12],
    [16.8,15.12,16.8,15.12,15.12,15.96,22.68,26.88,49.56,46.2,49.56,59.64,64.68,131.88,141.96,136.92,124.32,109.2,51.24,58.8,57.12,52.08,34.44,18.48],
    [21.0,20.16,19.32,19.32,18.48,39.48,41.16,104.16,128.52,141.96,153.72,148.68,186.48,213.36,221.76,192.36,200.76,180.6,137.76,144.48,141.96,129.36,78.96,25.2],
    [67.2,68.88,71.4,64.68,43.68,47.88,38.64,63.84,73.92,79.8,90.72,91.56,149.52,200.76,207.48,199.08,178.92,159.6,106.68,105.84,96.6,83.16,77.28,80.64],
    [24.36,25.2,24.36,24.36,24.36,23.52,27.72,172.2,173.04,91.56,95.76,106.68,171.36,223.44,238.56,226.8,199.08,180.6,110.88,85.68,78.96,71.4,51.24,25.2],
    [51.24,20.16,20.16,19.32,19.32,18.48,34.44,69.72,81.48,93.24,103.32,110.04,150.36,184.8,187.32,183.12,177.24,171.36,104.16,83.16,70.56,67.2,48.72,38.64],
  ],
  energia_ponta_kwh: [2662.80,5453.28,6108.06,4160.52,4073.58,2931.60,1882.23,4177.74,5302.71,5503.05,5112.45,3932.04],
  energia_fp_kwh: [12627.09,22532.58,25641.63,15337.77,14943.18,11676.42,9338.28,16476.39,21940.80,22099.56,23826.81,18554.55],
};

// Validação local (espelha backend modulos/load/service.py).
export function validarLoadLocal(p: InputLoadPayload): LoadResumo {
  const erros: string[] = [];
  if (p.demanda_kw.length !== 12)
    erros.push(`demanda_kw deve ter 12 meses (recebido: ${p.demanda_kw.length}).`);
  p.demanda_kw.forEach((linha, i) => {
    if (linha.length !== 24)
      erros.push(`demanda_kw[${i}] deve ter 24 horas (recebido: ${linha.length}).`);
  });
  if (p.energia_ponta_kwh.length !== 12)
    erros.push(`energia_ponta_kwh deve ter 12 meses (recebido: ${p.energia_ponta_kwh.length}).`);
  if (p.energia_fp_kwh.length !== 12)
    erros.push(`energia_fp_kwh deve ter 12 meses (recebido: ${p.energia_fp_kwh.length}).`);

  if (erros.length) {
    return {
      valido: false, erros,
      demanda_maxima_kw: 0, energia_ponta_total: 0, energia_fp_total: 0,
      energia_total: 0, energia_equivalente_kwh: [], pico_mensal_kw: [],
    };
  }

  const pico = p.demanda_kw.map((linha) => Math.max(0, ...linha));
  const demandaMax = p.demanda_maxima_kw ?? Math.max(0, ...pico);
  const pontaTotal = p.energia_ponta_kwh.reduce((a, b) => a + b, 0);
  const fpTotal = p.energia_fp_kwh.reduce((a, b) => a + b, 0);

  return {
    valido: true, erros: [],
    demanda_maxima_kw: demandaMax,
    energia_ponta_total: pontaTotal,
    energia_fp_total: fpTotal,
    energia_total: pontaTotal + fpTotal,
    energia_equivalente_kwh: p.energia_ponta_kwh.map((x, i) => x + p.energia_fp_kwh[i]),
    pico_mensal_kw: pico,
  };
}
