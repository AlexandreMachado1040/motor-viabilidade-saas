import { useMemo, useRef, useState } from "react";
import type { DiaDemanda } from "../../types";
import { fmt, INICIO_MES, MESES } from "./loadUtils";
import { C, niceCeil } from "./chartTheme";
import { ALFA_FP } from "./loadAnalise";

const W = 980, ML = 64, MR = 64, MT = 24, MB = 52;
const PW = W - ML - MR;
const DIAS_ANO = 366;

const xAno = (doy: number) => ML + ((doy - 1) / DIAS_ANO) * PW;

const dataBR = (d: DiaDemanda) =>
  `${String(d.dia).padStart(2, "0")}/${String(d.mes).padStart(2, "0")}`;

/** Caminho suave (Catmull-Rom → Bézier). */
function caminhoSuave(pts: { x: number; y: number }[]): string {
  if (pts.length === 0) return "";
  let d = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6, c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6, c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

interface Props {
  serie: DiaDemanda[];
  fonte: string;
  fp?: number; // se informado, o perfil horário decompõe P·Q·S no tooltip
}

export function DemandaDiariaChart({ serie, fonte, fp, selIndex, onHoverIndex, onPinIndex }: Props & {
  selIndex?: number; onHoverIndex?: (i: number | null) => void; onPinIndex?: (i: number) => void;
}) {
  const [hoverI, setHoverI] = useState<number | null>(null);
  const [fixoI, setFixoI] = useState<number | null>(null);

  const stats = useMemo(() => {
    let total = 0, iPico = 0, iMin = 0;
    serie.forEach((d, i) => {
      total += d.total_kwh;
      if (d.total_kwh > serie[iPico].total_kwh) iPico = i;
      if (d.total_kwh < serie[iMin].total_kwh) iMin = i;
    });
    return { total, iPico, iMin };
  }, [serie]);

  if (serie.length === 0) return null;

  // Modo controlado: a seleção de dia (timeline) vem do pai e é compartilhada
  // entre todos os gráficos. hoverI continua local só para exibir o tooltip deste.
  const ctrl = onHoverIndex != null;
  const sel = ctrl
    ? Math.max(0, Math.min(serie.length - 1, selIndex ?? stats.iPico))
    : (hoverI ?? fixoI ?? stats.iPico);
  const reportHover = (i: number | null) => { setHoverI(i); onHoverIndex?.(i); };
  const setPin = (i: number) => { if (ctrl) onPinIndex?.(i); else setFixoI(i); };
  const togglePin = (i: number) => { if (ctrl) onPinIndex?.(i); else setFixoI((f) => (f === i ? null : i)); };

  const diaMaisProximo = (e: React.MouseEvent, svg: SVGSVGElement | null) => {
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * W;
    const doy = 1 + ((mx - ML) / PW) * DIAS_ANO;
    let melhor = 0, dist = Infinity;
    serie.forEach((d, i) => {
      const dd = Math.abs(d.doy + 0.5 - doy);
      if (dd < dist) { dist = dd; melhor = i; }
    });
    reportHover(melhor);
  };

  return (
    <section className="painel">
      <GraficoDiario serie={serie} fonte={fonte} fp={fp} sel={sel} hover={hoverI} stats={stats}
        onMover={diaMaisProximo} onSair={() => reportHover(null)} onClicar={() => togglePin(sel)} />
      <SeletorDia serie={serie} sel={sel} onSel={setPin} />
      <PerfilHorario dia={serie[sel]} fp={fp} />
    </section>
  );
}

// ── Slider de seleção de dia (entre os dois gráficos, como no Aurova) ────────
function SeletorDia({ serie, sel, onSel }: { serie: DiaDemanda[]; sel: number; onSel: (i: number) => void }) {
  const dia = serie[sel];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "12px 2px 6px", flexWrap: "wrap" }}>
      <span style={{ fontSize: "0.82rem", color: C.muted }}>
        Dia: <strong style={{ color: C.cursor }}>{dataBR(dia)}</strong>
      </span>
      <input
        type="range" min={0} max={serie.length - 1} value={sel}
        onChange={(e) => onSel(Number(e.target.value))}
        style={{ flex: "1 1 0", minWidth: 160, accentColor: C.cursor }}
      />
      <span style={{ fontSize: "0.8rem", color: C.muted }}>
        Total: <strong>{fmt(dia.total_kwh)} kWh</strong> · Pico: <strong>{fmt(dia.pico_kw, 1)} kW</strong>
      </span>
    </div>
  );
}

type Handlers = {
  onMover: (e: React.MouseEvent, svg: SVGSVGElement | null) => void;
  onSair: () => void;
  onClicar: () => void;
};

// ── Topo: análise diária ao longo do ano (kWh/dia) ──────────────────────────
function GraficoDiario({
  serie, fonte, fp, sel, hover, stats, onMover, onSair, onClicar,
}: Props & { sel: number; hover: number | null; stats: { total: number; iPico: number; iMin: number } } & Handlers) {
  const ref = useRef<SVGSVGElement>(null);
  const temPQS = fp != null && fp > 0 && fp <= 1;
  const tanPhi = temPQS ? Math.tan(Math.acos(fp!)) : 0;
  const H = 300, PH = H - MT - MB;
  const media = stats.total / serie.length;
  // Com FP: decompõe a energia diária (P) em Q = P·tan(arccos FP) e S = P/FP.
  const yMax = niceCeil(Math.max(1, ...serie.map((d) => (temPQS ? d.total_kwh / fp! : d.total_kwh))));
  const y = (v: number) => MT + PH - (v / yMax) * PH;
  const pts = serie.map((d) => ({ x: xAno(d.doy), y: y(d.total_kwh) }));
  const linha = caminhoSuave(pts);
  const area = `${linha} L${pts[pts.length - 1].x.toFixed(1)},${MT + PH} L${pts[0].x.toFixed(1)},${MT + PH} Z`;
  const linhaQ = temPQS ? caminhoSuave(serie.map((d) => ({ x: xAno(d.doy), y: y(d.total_kwh * tanPhi) }))) : "";
  const linhaS = temPQS ? caminhoSuave(serie.map((d) => ({ x: xAno(d.doy), y: y(d.total_kwh / fp!) }))) : "";
  const ticks = Array.from({ length: 5 }, (_, i) => (yMax / 4) * i);
  const dia = serie[sel];
  const pico = serie[stats.iPico], minimo = serie[stats.iMin];
  const totalMWh = stats.total >= 1000;

  return (
    <>
      <h3>Análise diária — demanda ao longo do ano ({serie.length} dias)</h3>
      <p className="muted" style={{ marginTop: -6 }}>
        {fonte} · Total anual: {totalMWh ? `${fmt(stats.total / 1000, 1)} MWh` : `${fmt(stats.total)} kWh`}
        {" · "}Média/dia: {fmt(media)} kWh
        {" · "}Pico: {fmt(pico.total_kwh)} kWh ({dataBR(pico)})
        {" · "}Mínimo: {fmt(minimo.total_kwh)} kWh ({dataBR(minimo)})
      </p>
      <div style={{ background: C.painel, borderRadius: 10, padding: "8px 4px" }}>
        <svg ref={ref} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}
          onMouseMove={(e) => onMover(e, ref.current)} onMouseLeave={onSair} onClick={onClicar}>
          <defs>
            <linearGradient id="dailyFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.area0} /><stop offset="100%" stopColor={C.area1} />
            </linearGradient>
          </defs>
          <EixoMeses H={H} />
          <EixoY H={H} yMax={yMax} ticks={ticks} unidade="kWh" />
          <path d={area} fill="url(#dailyFill)" />
          <path d={linha} fill="none" stroke={C.linha} strokeWidth={2.2} strokeLinejoin="round" />
          {temPQS && <path d={linhaS} fill="none" stroke={C.acc} strokeWidth={1.8} strokeLinejoin="round" />}
          {temPQS && <path d={linhaQ} fill="none" stroke={C.media} strokeWidth={1.6} strokeDasharray="6 4" strokeLinejoin="round" />}
          {/* Média (âmbar) — oculta com P·Q·S para o âmbar não conflitar com o Q */}
          {!temPQS && (
            <>
              <line x1={ML} y1={y(media)} x2={ML + PW} y2={y(media)} stroke={C.media} strokeWidth={1.6} strokeDasharray="7 5" />
              <text x={ML + PW + 6} y={y(media) + 4} fontSize={12} fill={C.media}>Média {fmt(media)} kWh</text>
            </>
          )}
          {/* Pico (vermelho) */}
          <circle cx={xAno(pico.doy)} cy={y(pico.total_kwh)} r={4} fill={C.pico} stroke={C.bg} strokeWidth={1.5} />
          {/* Cursor do dia (ciano) */}
          <line x1={xAno(dia.doy)} y1={MT} x2={xAno(dia.doy)} y2={MT + PH} stroke={C.cursor} strokeWidth={1.5} />
          {temPQS && <circle cx={xAno(dia.doy)} cy={y(dia.total_kwh / fp!)} r={3.5} fill={C.acc} stroke={C.bg} strokeWidth={1.2} />}
          {temPQS && <circle cx={xAno(dia.doy)} cy={y(dia.total_kwh * tanPhi)} r={3.5} fill={C.media} stroke={C.bg} strokeWidth={1.2} />}
          <circle cx={xAno(dia.doy)} cy={y(dia.total_kwh)} r={4} fill={C.cursor} stroke={C.bg} strokeWidth={1.5} />
          <text x={xAno(dia.doy)} y={MT - 8} textAnchor="middle" fontSize={12} fill={C.cursor}>{dataBR(dia)}</text>
          {hover != null && (
            <Tip x={xAno(dia.doy)} y={y(dia.total_kwh)} H={H}
              linhas={
                temPQS
                  ? [
                      `Dia ${dataBR(dia)}`,
                      `P ativa (kWh) : ${fmt(dia.total_kwh, 2)}`,
                      `Q reativa (kVArh) : ${fmt(dia.total_kwh * tanPhi, 2)}`,
                      `S aparente (kVAh) : ${fmt(dia.total_kwh / fp!, 2)}`,
                    ]
                  : [`Dia ${dataBR(dia)}`, `${fmt(dia.total_kwh)} kWh · pico ${fmt(dia.pico_kw, 1)} kW`]
              }
              cores={temPQS ? [undefined, C.linha, C.media, C.acc] : undefined} />
          )}
          <text x={ML + PW / 2} y={H - 10} textAnchor="middle" fontSize={13} fill={C.txt}>Dia do ano</text>
        </svg>
        {temPQS && (
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: C.txt, padding: "2px 10px 4px" }}>
            <LegPQS cor={C.linha} rotulo="P ativa (kWh)" />
            <LegPQS cor={C.media} rotulo="Q reativa (kVArh)" tracejado />
            <LegPQS cor={C.acc} rotulo="S aparente (kVAh)" />
          </div>
        )}
      </div>
    </>
  );
}

// ── Baixo: perfil horário do dia selecionado (24 h, kW) — estilo Aurova ──────
// Layout local (margens próprias) para reproduzir o reference recharts sem
// afetar o gráfico diário, que usa as constantes compartilhadas.
const PML = 60, PMR = 24, PMT = 10, PMB = 50;
const PPW = W - PML - PMR;
const GRID_REF = "rgba(255,255,255,0.06)"; // grade tracejada translúcida do Aurova
const EIXO_REF = "#666";                    // linhas/rótulos de eixo do Aurova

function PerfilHorario({ dia, fp }: { dia: DiaDemanda; fp?: number }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hh, setHH] = useState<number | null>(null);
  const H = 230, PH = H - PMT - PMB;
  const base = PMT + PH;
  // Com FP (aba P·Q·S): decompõe a demanda (P) em Q = P·tan(arccos FP) e S = P/FP.
  const temPQS = fp != null && fp > 0 && fp <= 1;
  const tanPhi = temPQS ? Math.tan(Math.acos(fp!)) : 0;
  const pArr = dia.perfil_kw;
  const qArr = pArr.map((v) => v * tanPhi);
  const sArr = pArr.map((v) => (temPQS ? v / fp! : v));
  const yMax = niceCeil(Math.max(1, ...(temPQS ? sArr : pArr)));
  const y = (v: number) => PMT + PH - (v / yMax) * PH;
  const xh = (h: number) => PML + (h / 23) * PPW;
  const pts = pArr.map((v, h) => ({ x: xh(h), y: y(v) }));
  const linha = caminhoSuave(pts);
  const area = `${linha} L${pts[23].x.toFixed(1)},${base} L${pts[0].x.toFixed(1)},${base} Z`;
  const linhaQ = caminhoSuave(qArr.map((v, h) => ({ x: xh(h), y: y(v) })));
  const linhaS = caminhoSuave(sArr.map((v, h) => ({ x: xh(h), y: y(v) })));
  const ticks = Array.from({ length: 5 }, (_, i) => (yMax / 4) * i);
  const horas = Array.from({ length: 24 }, (_, h) => h);

  const aoMover = (e: React.MouseEvent) => {
    const svg = ref.current; if (!svg) return;
    const r = svg.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * W;
    const h = Math.round(((mx - PML) / PPW) * 23);
    setHH(Math.max(0, Math.min(23, h)));
  };

  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ background: C.painel, borderRadius: 10, padding: "8px 4px" }}>
        <svg ref={ref} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}
          onMouseMove={aoMover} onMouseLeave={() => setHH(null)}>
          <defs>
            <linearGradient id="dayHourFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.area0} /><stop offset="100%" stopColor={C.area1} />
            </linearGradient>
          </defs>

          {/* Grade horizontal + rótulos/tick do eixo Y */}
          {ticks.map((t) => (
            <g key={`y${t}`}>
              <line x1={PML} y1={y(t)} x2={PML + PPW} y2={y(t)} stroke={GRID_REF} strokeWidth={1} strokeDasharray="3 3" />
              <line x1={PML - 6} y1={y(t)} x2={PML} y2={y(t)} stroke={EIXO_REF} strokeWidth={1} />
              <text x={PML - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill={EIXO_REF}>{fmt(t)}{temPQS ? "" : " kW"}</text>
            </g>
          ))}
          {temPQS && <text x={PML - 6} y={PMT - 2} textAnchor="end" fontSize={9} fill={C.muted}>kW · kVAr · kVA</text>}

          {/* Grade vertical + rótulos/tick do eixo X em TODAS as 24 horas */}
          {horas.map((h) => (
            <g key={h}>
              <line x1={xh(h)} y1={PMT} x2={xh(h)} y2={base} stroke={GRID_REF} strokeWidth={1} strokeDasharray="3 3" />
              <line x1={xh(h)} y1={base} x2={xh(h)} y2={base + 6} stroke={EIXO_REF} strokeWidth={1} />
              <text x={xh(h)} y={base + 18} textAnchor="middle" fontSize={11} fill={EIXO_REF}>{h}h</text>
            </g>
          ))}

          {/* Eixos sólidos */}
          <line x1={PML} y1={base} x2={PML + PPW} y2={base} stroke={EIXO_REF} strokeWidth={1} />
          <line x1={PML} y1={PMT} x2={PML} y2={base} stroke={EIXO_REF} strokeWidth={1} />

          <path d={area} fill="url(#dayHourFill)" />
          {temPQS && <path d={linhaS} fill="none" stroke={C.acc} strokeWidth={1.8} strokeLinejoin="round" />}
          {temPQS && <path d={linhaQ} fill="none" stroke={C.media} strokeWidth={1.6} strokeDasharray="6 4" strokeLinejoin="round" />}
          <path d={linha} fill="none" stroke={C.linha} strokeWidth={2.2} strokeLinejoin="round" />

          {hh != null && (
            <>
              <line x1={xh(hh)} y1={PMT} x2={xh(hh)} y2={base} stroke={C.cursor} strokeWidth={1.2} />
              {temPQS && <circle cx={xh(hh)} cy={y(sArr[hh])} r={3.2} fill={C.acc} stroke={C.bg} strokeWidth={1.2} />}
              {temPQS && <circle cx={xh(hh)} cy={y(qArr[hh])} r={3.2} fill={C.media} stroke={C.bg} strokeWidth={1.2} />}
              <circle cx={xh(hh)} cy={y(dia.perfil_kw[hh])} r={3.5} fill={C.cursor} stroke={C.bg} strokeWidth={1.5} />
              <Tip x={xh(hh)} y={y(dia.perfil_kw[hh])} H={H}
                linhas={
                  temPQS
                    ? [
                        `${String(hh).padStart(2, "0")}:00 - ${String(hh).padStart(2, "0")}:59`,
                        `P ativa (kW) : ${fmt(pArr[hh], 2)}`,
                        `Q reativa (kVAr) : ${fmt(qArr[hh], 2)}`,
                        `S aparente (kVA) : ${fmt(sArr[hh], 2)}`,
                      ]
                    : [
                        `${String(hh).padStart(2, "0")}:00 - ${String(hh).padStart(2, "0")}:59`,
                        `Demanda : ${fmt(pArr[hh], 2)} kW`,
                      ]
                }
                cores={temPQS ? [undefined, C.linha, C.media, C.acc] : undefined} />
            </>
          )}

          <text x={PML + PPW / 2} y={H - 6} textAnchor="middle" fontSize={11} fill={C.muted}>
            Perfil horário — {dataBR(dia)}
          </text>
        </svg>
        {temPQS && (
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: C.txt, padding: "2px 10px 4px" }}>
            <LegPQS cor={C.linha} rotulo="P ativa (kW)" />
            <LegPQS cor={C.media} rotulo="Q reativa (kVAr)" tracejado />
            <LegPQS cor={C.acc} rotulo="S aparente (kVA)" />
          </div>
        )}
      </div>
    </div>
  );
}

function LegPQS({ cor, rotulo, tracejado }: { cor: string; rotulo: string; tracejado?: boolean }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{
        width: 16, height: 0, display: "inline-block",
        borderTop: `3px ${tracejado ? "dashed" : "solid"} ${cor}`,
      }} />
      {rotulo}
    </span>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// Fator de potência diário (cosφ) — visão anual + slider + perfil horário.
// Sem FP medido por dia, estima pelo modelo de carga baixa (Starosta/OSE):
//   cosφ(h) ≈ FP_nom · (P(h)/Dmáx)^ALFA_FP.
// ════════════════════════════════════════════════════════════════════════════
const FP_YMIN = 0.5, FP_YMAX = 1.02, FP_LIM = 0.92;

function fpDoDia(perfil: number[], fpNom: number): number[] {
  const dmax = Math.max(1e-9, ...perfil);
  return perfil.map((p) => (p <= 0 ? fpNom : Math.min(1, fpNom * Math.pow(p / dmax, ALFA_FP))));
}
function fpMedioDia(perfil: number[], fpNom: number): number {
  const fph = fpDoDia(perfil, fpNom);
  let e = 0, s = 0;
  perfil.forEach((p, h) => { e += p; s += fph[h] > 0 ? p / fph[h] : p; });
  return s > 0 ? e / s : fpNom;
}

export function CosphiDiarioChart({ serie, fpNom, fonte, selIndex, onHoverIndex, onPinIndex }: {
  serie: DiaDemanda[]; fpNom: number; fonte?: string;
  selIndex?: number; onHoverIndex?: (i: number | null) => void; onPinIndex?: (i: number) => void;
}) {
  const refAno = useRef<SVGSVGElement>(null);
  const [hoverI, setHoverI] = useState<number | null>(null);
  const [fixoI, setFixoI] = useState<number | null>(null);
  const fpDia = useMemo(() => serie.map((d) => fpMedioDia(d.perfil_kw, fpNom)), [serie, fpNom]);
  const stats = useMemo(() => {
    let iMin = 0, iMax = 0, soma = 0;
    fpDia.forEach((v, i) => { soma += v; if (v < fpDia[iMin]) iMin = i; if (v > fpDia[iMax]) iMax = i; });
    return { media: fpDia.length ? soma / fpDia.length : fpNom, iMin, iMax };
  }, [fpDia, fpNom]);

  if (serie.length === 0) return null;
  const ctrl = onHoverIndex != null;
  const sel = ctrl
    ? Math.max(0, Math.min(serie.length - 1, selIndex ?? stats.iMin))
    : (hoverI ?? fixoI ?? stats.iMin);
  const reportHover = (i: number | null) => { setHoverI(i); onHoverIndex?.(i); };
  const setPin = (i: number) => { if (ctrl) onPinIndex?.(i); else setFixoI(i); };
  const togglePin = (i: number) => { if (ctrl) onPinIndex?.(i); else setFixoI((f) => (f === i ? null : i)); };
  const H = 300, PH = H - MT - MB;
  const y = (v: number) => MT + PH - ((v - FP_YMIN) / (FP_YMAX - FP_YMIN)) * PH;
  const pts = serie.map((d, i) => ({ x: xAno(d.doy), y: y(fpDia[i]) }));
  const linha = caminhoSuave(pts);
  const ticksY = Array.from({ length: 5 }, (_, i) => FP_YMIN + ((FP_YMAX - FP_YMIN) / 4) * i);
  const dia = serie[sel];

  const aoMover = (e: React.MouseEvent) => {
    const svg = refAno.current; if (!svg) return;
    const r = svg.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * W;
    const doy = 1 + ((mx - ML) / PW) * DIAS_ANO;
    let melhor = 0, dist = Infinity;
    serie.forEach((d, i) => { const dd = Math.abs(d.doy + 0.5 - doy); if (dd < dist) { dist = dd; melhor = i; } });
    reportHover(melhor);
  };

  return (
    <section className="painel">
      <h3>Fator de potência diário — cosφ ao longo do ano ({serie.length} dias)</h3>
      <p className="muted" style={{ marginTop: -6 }}>
        {fonte ? `${fonte} · ` : ""}cosφ médio {fmt(stats.media, 3)} · mín {fmt(fpDia[stats.iMin], 3)} ({dataBR(serie[stats.iMin])})
        {" · "}máx {fmt(fpDia[stats.iMax], 3)} ({dataBR(serie[stats.iMax])}) · estimativa carga baixa cosφ(h) ≈ FP·(P/Dmáx)^{ALFA_FP}.
      </p>
      <div style={{ background: C.painel, borderRadius: 10, padding: "8px 4px" }}>
        <svg ref={refAno} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}
          onMouseMove={aoMover} onMouseLeave={() => reportHover(null)} onClick={() => togglePin(sel)}>
          <EixoMeses H={H} />
          {ticksY.map((t) => (
            <g key={t}>
              <line x1={ML} y1={y(t)} x2={ML + PW} y2={y(t)} stroke={C.grid} strokeWidth={1} strokeDasharray="1 4" />
              <text x={ML - 10} y={y(t) + 4} textAnchor="end" fontSize={12} fill={C.txt}>{fmt(t, 2)}</text>
            </g>
          ))}
          <text x={ML - 10} y={MT - 6} textAnchor="end" fontSize={9} fill={C.muted}>cosφ</text>
          <line x1={ML} y1={y(FP_LIM)} x2={ML + PW} y2={y(FP_LIM)} stroke={C.red} strokeWidth={1.6} strokeDasharray="6 4" />
          <text x={ML + PW + 6} y={y(FP_LIM) + 4} fontSize={12} fill={C.red}>Limite 0,92</text>
          <path d={linha} fill="none" stroke={C.media} strokeWidth={2.2} strokeLinejoin="round" />
          <line x1={xAno(dia.doy)} y1={MT} x2={xAno(dia.doy)} y2={MT + PH} stroke={C.cursor} strokeWidth={1.5} />
          <circle cx={xAno(dia.doy)} cy={y(fpDia[sel])} r={4} fill={C.cursor} stroke={C.bg} strokeWidth={1.5} />
          <text x={xAno(dia.doy)} y={MT - 8} textAnchor="middle" fontSize={12} fill={C.cursor}>{dataBR(dia)}</text>
          {hoverI != null && (
            <Tip x={xAno(dia.doy)} y={y(fpDia[sel])} H={H}
              linhas={[`Dia ${dataBR(dia)}`, `cosφ médio : ${fmt(fpDia[sel], 3)}`]}
              cores={[undefined, C.media]} />
          )}
          <text x={ML + PW / 2} y={H - 10} textAnchor="middle" fontSize={13} fill={C.txt}>Dia do ano</text>
        </svg>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "12px 2px 6px", flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.82rem", color: C.muted }}>Dia: <strong style={{ color: C.cursor }}>{dataBR(dia)}</strong></span>
        <input type="range" min={0} max={serie.length - 1} value={sel}
          onChange={(e) => setPin(Number(e.target.value))}
          style={{ flex: "1 1 0", minWidth: 160, accentColor: C.cursor }} />
        <span style={{ fontSize: "0.8rem", color: C.muted }}>
          cosφ médio do dia: <strong style={{ color: fpDia[sel] < FP_LIM ? C.red : C.linha }}>{fmt(fpDia[sel], 3)}</strong>
        </span>
      </div>

      <PerfilCosphi dia={dia} fpNom={fpNom} />
    </section>
  );
}

function PerfilCosphi({ dia, fpNom }: { dia: DiaDemanda; fpNom: number }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hh, setHH] = useState<number | null>(null);
  const H = 230, PH = H - PMT - PMB;
  const base = PMT + PH;
  const fph = fpDoDia(dia.perfil_kw, fpNom);
  const y = (v: number) => PMT + PH - ((v - FP_YMIN) / (FP_YMAX - FP_YMIN)) * PH;
  const xh = (h: number) => PML + (h / 23) * PPW;
  const pts = fph.map((v, h) => ({ x: xh(h), y: y(v) }));
  const linha = caminhoSuave(pts);
  const ticks = Array.from({ length: 5 }, (_, i) => FP_YMIN + ((FP_YMAX - FP_YMIN) / 4) * i);
  const horas = Array.from({ length: 24 }, (_, h) => h);

  const aoMover = (e: React.MouseEvent) => {
    const svg = ref.current; if (!svg) return;
    const r = svg.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * W;
    const h = Math.round(((mx - PML) / PPW) * 23);
    setHH(Math.max(0, Math.min(23, h)));
  };

  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ background: C.painel, borderRadius: 10, padding: "8px 4px" }}>
        <svg ref={ref} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}
          onMouseMove={aoMover} onMouseLeave={() => setHH(null)}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PML} y1={y(t)} x2={PML + PPW} y2={y(t)} stroke={GRID_REF} strokeWidth={1} strokeDasharray="3 3" />
              <line x1={PML - 6} y1={y(t)} x2={PML} y2={y(t)} stroke={EIXO_REF} strokeWidth={1} />
              <text x={PML - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill={EIXO_REF}>{fmt(t, 2)}</text>
            </g>
          ))}
          <text x={PML - 6} y={PMT - 2} textAnchor="end" fontSize={9} fill={C.muted}>cosφ</text>
          {horas.map((h) => (
            <g key={h}>
              <line x1={xh(h)} y1={PMT} x2={xh(h)} y2={base} stroke={GRID_REF} strokeWidth={1} strokeDasharray="3 3" />
              <line x1={xh(h)} y1={base} x2={xh(h)} y2={base + 6} stroke={EIXO_REF} strokeWidth={1} />
              <text x={xh(h)} y={base + 18} textAnchor="middle" fontSize={11} fill={EIXO_REF}>{h}h</text>
            </g>
          ))}
          <line x1={PML} y1={base} x2={PML + PPW} y2={base} stroke={EIXO_REF} strokeWidth={1} />
          <line x1={PML} y1={PMT} x2={PML} y2={base} stroke={EIXO_REF} strokeWidth={1} />
          <line x1={PML} y1={y(FP_LIM)} x2={PML + PPW} y2={y(FP_LIM)} stroke={C.red} strokeWidth={1.4} strokeDasharray="6 4" />
          <path d={linha} fill="none" stroke={C.media} strokeWidth={2} strokeLinejoin="round" />
          {hh != null && (
            <>
              <line x1={xh(hh)} y1={PMT} x2={xh(hh)} y2={base} stroke={C.cursor} strokeWidth={1.2} />
              <circle cx={xh(hh)} cy={y(fph[hh])} r={3.5} fill={C.media} stroke={C.bg} strokeWidth={1.5} />
              <Tip x={xh(hh)} y={y(fph[hh])} H={H}
                linhas={[`${String(hh).padStart(2, "0")}:00 - ${String(hh).padStart(2, "0")}:59`, `cosφ : ${fmt(fph[hh], 3)}`]}
                cores={[undefined, C.media]} />
            </>
          )}
          <text x={PML + PPW / 2} y={H - 6} textAnchor="middle" fontSize={11} fill={C.muted}>Perfil de cosφ — {dataBR(dia)}</text>
        </svg>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: C.txt, padding: "2px 10px 4px" }}>
          <LegPQS cor={C.media} rotulo="cosφ (estimado)" />
          <LegPQS cor={C.red} rotulo="Limite ANEEL 0,92" tracejado />
        </div>
      </div>
    </div>
  );
}

// ── Tooltip (caixa que segue o mouse) ───────────────────────────────────────
function Tip({ x, y, H, linhas, cores }: {
  x: number; y: number; H: number; linhas: string[]; cores?: (string | undefined)[];
}) {
  const temCor = !!cores;
  const w = Math.max(...linhas.map((l) => l.length)) * 6.4 + 16 + (temCor ? 12 : 0);
  const h = linhas.length * 15 + 8;
  let tx = x + 12; if (tx + w > ML + PW) tx = x - w - 12; if (tx < ML) tx = ML;
  let ty = y - h - 10; if (ty < MT) ty = y + 14; if (ty + h > H - MB) ty = H - MB - h;
  return (
    <g pointerEvents="none">
      <rect x={tx} y={ty} width={w} height={h} rx={6} fill="#0b1326" stroke={C.grid} />
      {linhas.map((l, i) => {
        const cor = cores?.[i];
        return (
          <g key={i}>
            {cor && <rect x={tx + 8} y={ty + 6 + i * 15} width={9} height={9} rx={2} fill={cor} />}
            <text x={tx + 8 + (cor ? 14 : 0)} y={ty + 15 + i * 15} fontSize={11} fill={C.txt}>{l}</text>
          </g>
        );
      })}
    </g>
  );
}

// ── Eixos compartilhados ────────────────────────────────────────────────────
function EixoMeses({ H }: { H: number }) {
  const PH = H - MT - MB;
  return (
    <>
      {MESES.map((m, i) => {
        const x0 = xAno(INICIO_MES[i]);
        const x1 = i < 11 ? xAno(INICIO_MES[i + 1]) : ML + PW;
        return (
          <g key={m}>
            <line x1={x0} y1={MT} x2={x0} y2={MT + PH} stroke={C.grid} strokeWidth={1} strokeDasharray="1 4" />
            <text x={(x0 + x1) / 2} y={MT + PH + 18} textAnchor="middle" fontSize={12} fill={C.txt}>{m}</text>
          </g>
        );
      })}
    </>
  );
}

function EixoY({ H, yMax, ticks, unidade }: { H: number; yMax: number; ticks: number[]; unidade: string }) {
  const PH = H - MT - MB;
  const y = (v: number) => MT + PH - (v / yMax) * PH;
  return (
    <>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={ML} y1={y(t)} x2={ML + PW} y2={y(t)} stroke={C.grid} strokeWidth={1} strokeDasharray="1 4" />
          <text x={ML - 10} y={y(t) - 1} textAnchor="end" fontSize={12} fill={C.txt}>{fmt(t)}</text>
          <text x={ML - 10} y={y(t) + 12} textAnchor="end" fontSize={10} fill={C.muted}>{unidade}</text>
        </g>
      ))}
    </>
  );
}
