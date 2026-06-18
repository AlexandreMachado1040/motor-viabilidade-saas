import type { DiaDemanda, InputLoadPayload } from "../../types";
import { parseNumeroBR } from "./loadUtils";

// Recurso "ctr-curvas-carga-redes-tipo.csv" no DataStore (CKAN) da ANEEL.
const RID = "a77cacce-6a49-44c7-af20-508aecd4539d";

export const SUBGRUPOS = ["A2", "A3", "A4"] as const;

// 43 distribuidoras presentes no recurso (levantadas via API, distinct SigCcs).
export const DISTRIBUIDORAS = [
  "AES SUL", "AME", "BANDEIRANTE", "CAIUÁ", "CEAL", "CEB", "CEEE", "CELESC",
  "CELG", "CELPA", "CELTINS", "CEMAT", "CEMIG", "CERON", "CHESP", "CNEE",
  "COCEL", "COELCE", "COPEL", "COSERN", "CPEE", "CPFL MOCOCA", "CPFL PAULISTA",
  "CPFL PIRATININGA", "CPFL SANTA CRUZ", "CPFL SUL PAULISTA", "EFLJC", "EFLUL",
  "ELETROACRE", "ELETROCAR", "ELETROPAULO", "ELFSM", "EMG", "ENERGISA BORBOREMA",
  "ENERSUL", "ENF", "EPB", "ESCELSA", "ESE", "HIDROPAN", "IENERGIA",
  "MUX ENERGIA", "UHENPAL",
];

const TIPOS_DIA = ["Dia Útil", "Sábado", "Domingo"] as const;
type TipoDia = (typeof TIPOS_DIA)[number];

const PONTA_HORAS = new Set([18, 19, 20]); // seg–sex 18h–21h

export interface CampanhaResultado {
  payload: InputLoadPayload;
  serieDiaria: DiaDemanda[];
  meta: { sig: string; sbg: string; demandante: string; ano: string; processo: string };
}

interface DSResult {
  records: Record<string, string>[];
  total: number;
}

async function ds(paramsObj: Record<string, string>): Promise<DSResult> {
  const usp = new URLSearchParams({ resource_id: RID, ...paramsObj });
  const r = await fetch(`/aneel/api/3/action/datastore_search?${usp.toString()}`);
  if (!r.ok) throw new Error(`ANEEL HTTP ${r.status}`);
  const j = await r.json();
  if (!j?.success) throw new Error("ANEEL: resposta sem sucesso");
  return j.result as DSResult;
}

/** Lista os "demandantes" (Rede/Consumidor Tipo) de uma distribuidora + subgrupo. */
export async function listarDemandantes(sig: string, sbg: string): Promise<string[]> {
  const res = await ds({
    fields: "DscDemandante", distinct: "true", limit: "200",
    filters: JSON.stringify({ SigCcs: sig, NomSbgDes: sbg }),
  });
  return res.records.map((r) => r.DscDemandante).filter(Boolean).sort();
}

/** Escolhe o processo mais recente (ano máximo) para a combinação. */
async function escolherProcesso(sig: string, sbg: string, dem: string) {
  const res = await ds({
    fields: "AnoPrcCal,DscPrcCal", distinct: "true", limit: "200",
    filters: JSON.stringify({ SigCcs: sig, NomSbgDes: sbg, DscDemandante: dem }),
  });
  if (res.records.length === 0) throw new Error("Sem processo de cálculo para a seleção.");
  let melhor = res.records[0];
  for (const r of res.records) if (+r.AnoPrcCal > +melhor.AnoPrcCal) melhor = r;
  return { ano: melhor.AnoPrcCal, processo: melhor.DscPrcCal };
}

/** Baixa as 3 curvas (Útil/Sábado/Domingo) e agrega cada uma em 24 valores horários. */
async function curvasHorarias(sig: string, sbg: string, dem: string, ano: string, processo: string) {
  const res = await ds({
    limit: "400",
    filters: JSON.stringify({
      SigCcs: sig, NomSbgDes: sbg, DscDemandante: dem, AnoPrcCal: ano, DscPrcCal: processo,
    }),
  });
  const soma: Record<string, number[]> = {};
  const cnt: Record<string, number[]> = {};
  for (const t of TIPOS_DIA) { soma[t] = Array(24).fill(0); cnt[t] = Array(24).fill(0); }
  for (const rec of res.records) {
    const tipo = rec.DscTipoDia as TipoDia;
    if (!soma[tipo]) continue;
    const h = parseInt(String(rec.HorInicial).slice(0, 2), 10);
    if (Number.isNaN(h) || h < 0 || h > 23) continue;
    const v = parseNumeroBR(rec.VlrDmd);
    soma[tipo][h] += v; cnt[tipo][h] += 1;
  }
  const horaria: Record<TipoDia, number[]> = { "Dia Útil": [], "Sábado": [], "Domingo": [] };
  for (const t of TIPOS_DIA) {
    horaria[t] = soma[t].map((s, h) => (cnt[t][h] > 0 ? s / cnt[t][h] : 0));
  }
  // Fallback: se faltar Sábado/Domingo, usa o Dia Útil.
  const util = horaria["Dia Útil"];
  if (horaria["Sábado"].every((x) => x === 0)) horaria["Sábado"] = util;
  if (horaria["Domingo"].every((x) => x === 0)) horaria["Domingo"] = util;
  return horaria;
}

function tipoDoDia(weekday: number): TipoDia {
  if (weekday === 0) return "Domingo";
  if (weekday === 6) return "Sábado";
  return "Dia Útil";
}

/** Carrega a campanha de medição e monta o InputLoad (matriz 12×24 + energia + série diária). */
export async function carregarCampanha(sig: string, sbg: string, dem: string): Promise<CampanhaResultado> {
  const { ano, processo } = await escolherProcesso(sig, sbg, dem);
  const horaria = await curvasHorarias(sig, sbg, dem, ano, processo);

  // Ano representativo (2025, 365 dias contíguos) — perfil de cada dia pelo tipo (Útil/Sáb/Dom).
  const serieDiaria: DiaDemanda[] = [];
  const soma = Array.from({ length: 12 }, () => Array<number>(24).fill(0));
  const cnt = Array.from({ length: 12 }, () => Array<number>(24).fill(0));
  const ponta = Array<number>(12).fill(0);
  const fp = Array<number>(12).fill(0);
  let maxKw = 0;

  for (let k = 0; k < 365; k++) {
    const dt = new Date(2025, 0, 1 + k);
    const mes = dt.getMonth() + 1, dia = dt.getDate(), wd = dt.getDay();
    const perfil = horaria[tipoDoDia(wd)];
    let total = 0, pico = 0;
    for (let h = 0; h < 24; h++) {
      const kw = perfil[h] ?? 0;
      total += kw;
      if (kw > pico) pico = kw;
      if (kw > maxKw) maxKw = kw;
      soma[mes - 1][h] += kw; cnt[mes - 1][h] += 1;
      const ehPonta = wd >= 1 && wd <= 5 && PONTA_HORAS.has(h);
      if (ehPonta) ponta[mes - 1] += kw; else fp[mes - 1] += kw;
    }
    serieDiaria.push({
      ano: 2025, mes, dia, doy: k + 1,
      total_kwh: +total.toFixed(2), pico_kw: +pico.toFixed(2),
      perfil_kw: perfil.map((v) => +v.toFixed(2)),
    });
  }

  const demanda_kw = soma.map((lin, m) =>
    lin.map((s, h) => (cnt[m][h] > 0 ? +(s / cnt[m][h]).toFixed(2) : 0)));

  return {
    payload: {
      demanda_maxima_kw: +maxKw.toFixed(2),
      demanda_kw,
      energia_ponta_kwh: ponta.map((v) => +v.toFixed(2)),
      energia_fp_kwh: fp.map((v) => +v.toFixed(2)),
    },
    serieDiaria,
    meta: { sig, sbg, demandante: dem, ano, processo },
  };
}
