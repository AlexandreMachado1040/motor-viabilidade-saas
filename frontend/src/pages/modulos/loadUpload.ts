import * as XLSX from "xlsx";
import type { DiaDemanda, FPInfo, InputLoadPayload } from "../../types";
import { diaDoAno } from "./loadUtils";

export interface ResultadoUpload {
  ok: boolean;
  tipo: "distribuidora" | "desconhecido";
  payload?: InputLoadPayload;
  serieDiaria?: DiaDemanda[];
  fp?: FPInfo;
  aviso: string;
}

// Fallback de ponta quando o arquivo não traz "Postos horários": seg–sex 18h–21h.
const PONTA_HORAS = new Set([18, 19, 20]);

/** lowercase + remove acentos/mojibake → tolerante a Latin-1/UTF-8. */
function norm(s: unknown): string {
  return String(s ?? "").toLowerCase().normalize("NFD")
    .replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9 ]/g, " ")
    .replace(/\s+/g, " ").trim();
}

/**
 * Converte célula em número detectando o separador decimal — PONTO ou VÍRGULA.
 * Regra: quando há os dois, o que aparece por último é o decimal e o outro é
 * separador de milhar ("1.234,56" e "1,234.56" → 1234.56). Com só um tipo, a
 * última ocorrência é o decimal e as anteriores são milhar.
 */
function celulaNumero(c: unknown): number | null {
  let s = String(c ?? "").trim();
  if (s === "" || s === "-") return null;
  if (!/\d/.test(s)) return null;
  s = s.replace(/\s/g, "");
  const ld = s.lastIndexOf("."), lc = s.lastIndexOf(",");
  if (ld >= 0 && lc >= 0) {
    s = lc > ld
      ? s.replace(/\./g, "").replace(",", ".")  // vírgula é o decimal (pt-BR)
      : s.replace(/,/g, "");                      // ponto é o decimal (intl)
  } else if (lc >= 0) {
    s = s.slice(0, lc).replace(/,/g, "") + "." + s.slice(lc + 1);
  } else if (ld >= 0 && (s.match(/\./g) || []).length > 1) {
    s = s.slice(0, ld).replace(/\./g, "") + "." + s.slice(ld + 1);
  }
  if (!/^-?\d+(\.\d+)?$/.test(s)) return null;
  const v = Number(s);
  return Number.isNaN(v) ? null : v;
}

function parseMomento(dataCell: string, timeCell?: string):
  { ano: number; mes: number; dia: number; hora: number } | null {
  const s = String(dataCell ?? "").trim();
  let dia = 0, mes = 0, ano = 0;
  let hora: number | null = null;
  let m = s.match(/(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(?:[ T]+(\d{1,2}):(\d{2}))?/);
  if (m) { dia = +m[1]; mes = +m[2]; ano = +m[3]; if (m[4] != null) hora = +m[4]; }
  else {
    m = s.match(/(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})(?:[ T]+(\d{1,2}):(\d{2}))?/);
    if (!m) return null;
    ano = +m[1]; mes = +m[2]; dia = +m[3]; if (m[4] != null) hora = +m[4];
  }
  if (hora == null && timeCell) {
    const t = String(timeCell).match(/(\d{1,2}):(\d{2})/);
    if (t) hora = +t[1];
  }
  if (hora == null) return null;
  if (ano < 100) ano += 2000;
  if (mes < 1 || mes > 12 || dia < 1 || dia > 31 || hora < 0 || hora > 23) return null;
  return { ano, mes, dia, hora };
}

/** Escolhe o delimitador (`;`, tab ou `,`) que melhor divide as linhas em colunas. */
function detectarDelimitador(linhas: string[]): string {
  const cands = [";", "\t", ","];
  const amostra = linhas.slice(0, 8);
  let melhor = ";", melhorCols = 0;
  for (const d of cands) {
    const cols = amostra.map((l) => l.split(d).length).sort((a, b) => a - b);
    const mediana = cols[Math.floor(cols.length / 2)] || 1; // robusta a linhas atípicas
    if (mediana > melhorCols) { melhorCols = mediana; melhor = d; }
  }
  return melhor;
}

/** Lê o arquivo (CSV/TSV/TXT com detecção de encoding, ou XLSX) → matriz de strings. */
export async function lerPlanilha(file: File): Promise<string[][]> {
  const nome = file.name.toLowerCase();
  if (nome.endsWith(".xlsx") || nome.endsWith(".xls")) {
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf, { type: "array" });
    const ws = wb.Sheets[wb.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json<unknown[]>(ws, { header: 1, raw: false, defval: "" });
    return rows.map((r) => (r as unknown[]).map((c) => (c == null ? "" : String(c))));
  }
  const buf = await file.arrayBuffer();
  let texto = new TextDecoder("utf-8").decode(buf);
  if (texto.includes("�")) texto = new TextDecoder("windows-1252").decode(buf);
  const linhas = texto.split(/\r?\n/).filter((l) => l.trim().length > 0);
  const delim = detectarDelimitador(linhas);
  return linhas.map((l) => l.split(delim).map((c) => c.trim()));
}

/** Auto-detecta o formato e devolve o InputLoadPayload preenchido. */
export function interpretar(rows: string[][]): ResultadoUpload {
  let head = -1;
  for (let i = 0; i < Math.min(rows.length, 12); i++) {
    const cols = rows[i].map(norm);
    const temData = cols.some((c) => c === "data" || c.startsWith("data"));
    const temVal = cols.some((c) => /\bkw\b|kwh|demanda|potencia|ativa|consumo/.test(c));
    if (temData && temVal) { head = i; break; }
  }

  if (head >= 0) {
    const cab = rows[head].map(norm);
    const dateIdx = cab.findIndex((c) => c === "data" || c.startsWith("data"));
    const horaIdx = cab.findIndex((c) => c.startsWith("hora"));
    const postoIdx = cab.findIndex((c) => c.includes("posto"));
    let valIdx = cab.findIndex((c) => c.includes("forneci") && (c.includes("kwh") || c.includes("kw")));
    if (valIdx < 0) valIdx = cab.findIndex((c) => c.includes("ativa") && c.includes("consumo"));
    if (valIdx < 0) valIdx = cab.findIndex((c) => c.includes("demanda") || c.includes("potencia"));
    if (valIdx < 0) valIdx = cab.findIndex((c, i) =>
      i !== dateIdx && i !== horaIdx && i !== postoIdx && /kwh|\bkw\b/.test(c));
    const isEnergia = valIdx >= 0 && (cab[valIdx].includes("kwh") || cab[valIdx].includes("consumo"));
    // Colunas de reativa (kVAr/kVArh) fornecida — indutivo e capacitivo.
    const qIndIdx = cab.findIndex((c) => /kvar/.test(c) && c.includes("indutivo") && !c.includes("receb"));
    const qCapIdx = cab.findIndex((c) => /kvar/.test(c) && c.includes("capacit") && !c.includes("receb"));
    if (dateIdx >= 0 && valIdx >= 0) {
      return agregar(rows.slice(head + 1), { dateIdx, horaIdx, postoIdx, valIdx, isEnergia, qIndIdx, qCapIdx });
    }
  }

  return {
    ok: false, tipo: "desconhecido",
    aviso: "Formato não reconhecido. Esperado: export de demanda/consumo (coluna Data + kW/kWh).",
  };
}

interface Cols { dateIdx: number; horaIdx: number; postoIdx: number; valIdx: number; isEnergia: boolean; qIndIdx: number; qCapIdx: number; }

function agregar(body: string[][], c: Cols): ResultadoUpload {
  interface T { ano: number; mes: number; dia: number; hora1b: number | null; horaTs: number | null; val: number; qInd: number; qCap: number; posto: string; }
  const tmp: T[] = [];
  const horas1b = new Set<number>();
  const temReativa = c.qIndIdx >= 0 || c.qCapIdx >= 0;

  for (const r of body) {
    const val = celulaNumero(r[c.valIdx]);
    if (val == null) continue;
    const mom = parseMomento(r[c.dateIdx] ?? "", c.horaIdx >= 0 ? r[c.horaIdx] : undefined);
    let hora1b: number | null = null;
    if (c.horaIdx >= 0) {
      const hn = celulaNumero(r[c.horaIdx]);
      if (hn != null) { hora1b = Math.round(hn); horas1b.add(hora1b); }
    }
    if (!mom) continue;
    tmp.push({
      ano: mom.ano, mes: mom.mes, dia: mom.dia,
      hora1b, horaTs: mom.hora, val,
      qInd: c.qIndIdx >= 0 ? Math.abs(celulaNumero(r[c.qIndIdx]) ?? 0) : 0,
      qCap: c.qCapIdx >= 0 ? Math.abs(celulaNumero(r[c.qCapIdx]) ?? 0) : 0,
      posto: norm(c.postoIdx >= 0 ? r[c.postoIdx] : ""),
    });
  }

  if (tmp.length === 0) {
    return { ok: false, tipo: "desconhecido", aviso: "Nenhuma leitura válida encontrada no arquivo." };
  }

  const arr = [...horas1b];
  const oneBased = arr.length > 0 && Math.max(...arr) >= 24 && Math.min(...arr) >= 1;

  // Δt: maior nº de leituras numa mesma (data, hora) → intervalo
  const bucket = new Map<string, number>();
  const resolved = tmp.map((t) => {
    let hora = t.hora1b != null ? (oneBased ? t.hora1b - 1 : t.hora1b) : (t.horaTs ?? 0);
    hora = ((hora % 24) + 24) % 24;
    const k = `${t.ano}-${t.mes}-${t.dia}-${hora}`;
    bucket.set(k, (bucket.get(k) || 0) + 1);
    return { ...t, hora };
  });
  const dt = 1 / Math.max(1, ...bucket.values());

  const soma = Array.from({ length: 12 }, () => Array(24).fill(0));
  const cnt = Array.from({ length: 12 }, () => Array(24).fill(0));
  const pAM = new Map<string, number>();
  const fAM = new Map<string, number>();
  let maxKw = 0;
  let usaPosto = false;

  // Acumuladores de FP (reativa): por hora e por posto.
  const somaPh = Array(24).fill(0), somaQh = Array(24).fill(0);
  const somaQindh = Array(24).fill(0), somaQcaph = Array(24).fill(0);
  const cntPh = Array(24).fill(0);
  let totP = 0, totQ = 0, eaPonta = 0, erPonta = 0, eaFora = 0, erFora = 0;

  // Acúmulo por dia real (chave ano-mês-dia) → série diária ao longo do ano.
  interface DiaAcc { ano: number; mes: number; dia: number; kwh: number; pico: number; soma: number[]; cnt: number[]; }
  const dias = new Map<string, DiaAcc>();

  for (const t of resolved) {
    const kw = c.isEnergia ? t.val / dt : t.val;
    const kwh = c.isEnergia ? t.val : t.val * dt;
    soma[t.mes - 1][t.hora] += kw;
    cnt[t.mes - 1][t.hora] += 1;
    if (kw > maxKw) maxKw = kw;

    const dk = `${t.ano}-${t.mes}-${t.dia}`;
    let d = dias.get(dk);
    if (!d) { d = { ano: t.ano, mes: t.mes, dia: t.dia, kwh: 0, pico: 0, soma: Array(24).fill(0), cnt: Array(24).fill(0) }; dias.set(dk, d); }
    d.kwh += kwh;
    if (kw > d.pico) d.pico = kw;
    d.soma[t.hora] += kw;
    d.cnt[t.hora] += 1;

    let ehPonta: boolean;
    if (c.postoIdx >= 0 && t.posto) {
      usaPosto = true;
      ehPonta = t.posto.includes("ponta") && !t.posto.includes("fora");
    } else {
      const wd = new Date(t.ano, t.mes - 1, t.dia).getDay();
      ehPonta = wd >= 1 && wd <= 5 && PONTA_HORAS.has(t.hora);
    }
    const am = `${t.ano}-${t.mes}`;
    const mapa = ehPonta ? pAM : fAM;
    mapa.set(am, (mapa.get(am) || 0) + kwh);

    // Reativa (kVAr) na mesma escala de potência da curva.
    const qkvar = c.isEnergia ? (t.qInd + t.qCap) / dt : (t.qInd + t.qCap);
    somaPh[t.hora] += kw; somaQh[t.hora] += qkvar; cntPh[t.hora] += 1;
    somaQindh[t.hora] += c.isEnergia ? t.qInd / dt : t.qInd;
    somaQcaph[t.hora] += c.isEnergia ? t.qCap / dt : t.qCap;
    totP += kw; totQ += qkvar;
    if (ehPonta) { eaPonta += kw; erPonta += qkvar; } else { eaFora += kw; erFora += qkvar; }
  }

  const matriz = soma.map((lin, m) =>
    lin.map((s, h) => (cnt[m][h] > 0 ? +(s / cnt[m][h]).toFixed(2) : 0)));

  // energia representativa por mês: média entre os anos presentes (evita dupla contagem)
  const ponta = Array(12).fill(0);
  const fp = Array(12).fill(0);
  for (let mes = 1; mes <= 12; mes++) {
    const anos = new Set<number>();
    for (const k of [...pAM.keys(), ...fAM.keys()]) {
      const [a, mm] = k.split("-").map(Number);
      if (mm === mes) anos.add(a);
    }
    if (anos.size === 0) continue;
    let sp = 0, sf = 0;
    for (const a of anos) { sp += pAM.get(`${a}-${mes}`) || 0; sf += fAM.get(`${a}-${mes}`) || 0; }
    ponta[mes - 1] = +(sp / anos.size).toFixed(2);
    fp[mes - 1] = +(sf / anos.size).toFixed(2);
  }

  // Série diária: colapsa múltiplos anos num ano representativo (média por mês-dia).
  interface Grp { mes: number; dia: number; kwh: number; pico: number; n: number; soma: number[]; cnt: number[]; }
  const grp = new Map<string, Grp>();
  for (const d of dias.values()) {
    const k = `${d.mes}-${d.dia}`;
    let g = grp.get(k);
    if (!g) { g = { mes: d.mes, dia: d.dia, kwh: 0, pico: 0, n: 0, soma: Array(24).fill(0), cnt: Array(24).fill(0) }; grp.set(k, g); }
    g.kwh += d.kwh; g.pico += d.pico; g.n += 1;
    for (let h = 0; h < 24; h++) { g.soma[h] += d.soma[h]; g.cnt[h] += d.cnt[h]; }
  }
  const serieDiaria: DiaDemanda[] = [...grp.values()].map((g) => ({
    ano: 0, mes: g.mes, dia: g.dia, doy: diaDoAno(g.mes, g.dia),
    total_kwh: +(g.kwh / g.n).toFixed(2),
    pico_kw: +(g.pico / g.n).toFixed(2),
    perfil_kw: g.soma.map((s, h) => (g.cnt[h] > 0 ? +(s / g.cnt[h]).toFixed(2) : 0)),
  })).sort((a, b) => a.doy - b.doy);

  // Fator de potência (se o arquivo trouxe colunas de reativa).
  const fpDe = (ea: number, er: number) => { const s = Math.hypot(ea, er); return s > 0 ? +(ea / s).toFixed(4) : 1; };
  let fpInfo: FPInfo | undefined;
  if (temReativa && totQ > 0) {
    const pPorHora = somaPh.map((s, h) => (cntPh[h] > 0 ? +(s / cntPh[h]).toFixed(2) : 0));
    const qPorHora = somaQh.map((s, h) => (cntPh[h] > 0 ? +(s / cntPh[h]).toFixed(2) : 0));
    fpInfo = {
      pPorHora, qPorHora,
      fpPorHora: pPorHora.map((p, h) => fpDe(p, qPorHora[h])),
      capPorHora: somaQcaph.map((cc, h) => cc > somaQindh[h]),
      medio: fpDe(totP, totQ),
      ponta: fpDe(eaPonta, erPonta),
      fora: fpDe(eaFora, erFora),
      fonte: c.isEnergia ? "consumo (kVArh)" : "demanda (kVAr)",
    };
  }

  const classif = usaPosto ? "Ponta/Fora-Ponta do arquivo" : "ponta estimada (seg–sex 18h–21h)";
  const tipoVal = c.isEnergia ? "consumo (kWh)" : "demanda (kW)";
  const avisoFP = fpInfo ? ` FP médio ${fpInfo.medio.toFixed(3)} (ponta ${fpInfo.ponta.toFixed(3)} · fora ${fpInfo.fora.toFixed(3)}).` : "";
  return {
    ok: true, tipo: "distribuidora",
    payload: {
      demanda_maxima_kw: +maxKw.toFixed(2), demanda_kw: matriz,
      energia_ponta_kwh: ponta, energia_fp_kwh: fp,
    },
    serieDiaria,
    fp: fpInfo,
    aviso: `Importado ${tipoVal}: ${resolved.length.toLocaleString("pt-BR")} leituras · `
      + `intervalo ${Math.round(dt * 60)} min · ${classif}. Demanda mensal/horária e energia mensal preenchidas.${avisoFP}`,
  };
}

