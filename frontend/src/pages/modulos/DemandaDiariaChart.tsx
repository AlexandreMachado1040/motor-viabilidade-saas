import { useMemo, useRef, useState } from "react";
import type { DiaDemanda } from "../../types";
import { fmt, INICIO_MES, MESES } from "./loadUtils";
import { C, niceCeil } from "./chartTheme";

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
}

export function DemandaDiariaChart({ serie, fonte }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const [fixo, setFixo] = useState<number | null>(null);

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

  const sel = hover ?? fixo ?? stats.iPico;

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
    setHover(melhor);
  };
  const aoClicar = () => setFixo((f) => (f === sel ? null : sel));

  return (
    <section className="painel">
      <GraficoDiario serie={serie} fonte={fonte} sel={sel} hover={hover} stats={stats}
        onMover={diaMaisProximo} onSair={() => setHover(null)} onClicar={aoClicar} />
      <SeletorDia serie={serie} sel={sel} onSel={setFixo} />
      <PerfilHorario dia={serie[sel]} />
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
  serie, fonte, sel, hover, stats, onMover, onSair, onClicar,
}: Props & { sel: number; hover: number | null; stats: { total: number; iPico: number; iMin: number } } & Handlers) {
  const ref = useRef<SVGSVGElement>(null);
  const H = 300, PH = H - MT - MB;
  const media = stats.total / serie.length;
  const yMax = niceCeil(Math.max(1, ...serie.map((d) => d.total_kwh)));
  const y = (v: number) => MT + PH - (v / yMax) * PH;
  const pts = serie.map((d) => ({ x: xAno(d.doy), y: y(d.total_kwh) }));
  const linha = caminhoSuave(pts);
  const area = `${linha} L${pts[pts.length - 1].x.toFixed(1)},${MT + PH} L${pts[0].x.toFixed(1)},${MT + PH} Z`;
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
          {/* Média (âmbar) */}
          <line x1={ML} y1={y(media)} x2={ML + PW} y2={y(media)} stroke={C.media} strokeWidth={1.6} strokeDasharray="7 5" />
          <text x={ML + PW + 6} y={y(media) + 4} fontSize={12} fill={C.media}>Média {fmt(media)} kWh</text>
          {/* Pico (vermelho) */}
          <circle cx={xAno(pico.doy)} cy={y(pico.total_kwh)} r={4} fill={C.pico} stroke={C.bg} strokeWidth={1.5} />
          {/* Cursor do dia (ciano) */}
          <line x1={xAno(dia.doy)} y1={MT} x2={xAno(dia.doy)} y2={MT + PH} stroke={C.cursor} strokeWidth={1.5} />
          <circle cx={xAno(dia.doy)} cy={y(dia.total_kwh)} r={4} fill={C.cursor} stroke={C.bg} strokeWidth={1.5} />
          <text x={xAno(dia.doy)} y={MT - 8} textAnchor="middle" fontSize={12} fill={C.cursor}>{dataBR(dia)}</text>
          {hover != null && (
            <Tip x={xAno(dia.doy)} y={y(dia.total_kwh)} H={H}
              linhas={[`Dia ${dataBR(dia)}`, `${fmt(dia.total_kwh)} kWh · pico ${fmt(dia.pico_kw, 1)} kW`]} />
          )}
          <text x={ML + PW / 2} y={H - 10} textAnchor="middle" fontSize={13} fill={C.txt}>Dia do ano</text>
        </svg>
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

function PerfilHorario({ dia }: { dia: DiaDemanda }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hh, setHH] = useState<number | null>(null);
  const H = 230, PH = H - PMT - PMB;
  const base = PMT + PH;
  const yMax = niceCeil(Math.max(1, ...dia.perfil_kw));
  const y = (v: number) => PMT + PH - (v / yMax) * PH;
  const xh = (h: number) => PML + (h / 23) * PPW;
  const pts = dia.perfil_kw.map((v, h) => ({ x: xh(h), y: y(v) }));
  const linha = caminhoSuave(pts);
  const area = `${linha} L${pts[23].x.toFixed(1)},${base} L${pts[0].x.toFixed(1)},${base} Z`;
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
              <stop offset="0%" stopColor="#00C8FF" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#005FFF" stopOpacity={0.05} />
            </linearGradient>
          </defs>

          {/* Grade horizontal + rótulos/tick do eixo Y */}
          {ticks.map((t) => (
            <g key={`y${t}`}>
              <line x1={PML} y1={y(t)} x2={PML + PPW} y2={y(t)} stroke={GRID_REF} strokeWidth={1} strokeDasharray="3 3" />
              <line x1={PML - 6} y1={y(t)} x2={PML} y2={y(t)} stroke={EIXO_REF} strokeWidth={1} />
              <text x={PML - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill={EIXO_REF}>{fmt(t)} kW</text>
            </g>
          ))}

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

          <path d={area} fill="url(#dayHourFill)" fillOpacity={0.6} />
          <path d={linha} fill="none" stroke="#00C8FF" strokeWidth={2} strokeLinejoin="round" />

          {hh != null && (
            <>
              <line x1={xh(hh)} y1={PMT} x2={xh(hh)} y2={base} stroke={C.cursor} strokeWidth={1.2} />
              <circle cx={xh(hh)} cy={y(dia.perfil_kw[hh])} r={3.5} fill={C.cursor} stroke={C.bg} strokeWidth={1.5} />
              <Tip x={xh(hh)} y={y(dia.perfil_kw[hh])} H={H}
                linhas={[`${hh}h–${hh + 1}h`, `${fmt(dia.perfil_kw[hh], 1)} kW`]} />
            </>
          )}

          <text x={PML + PPW / 2} y={H - 6} textAnchor="middle" fontSize={11} fill={C.muted}>
            Perfil horário — {dataBR(dia)}
          </text>
        </svg>
      </div>
    </div>
  );
}

// ── Tooltip (caixa que segue o mouse) ───────────────────────────────────────
function Tip({ x, y, H, linhas }: { x: number; y: number; H: number; linhas: string[] }) {
  const w = Math.max(...linhas.map((l) => l.length)) * 6.4 + 16;
  const h = linhas.length * 15 + 8;
  let tx = x + 12; if (tx + w > ML + PW) tx = x - w - 12; if (tx < ML) tx = ML;
  let ty = y - h - 10; if (ty < MT) ty = y + 14; if (ty + h > H - MB) ty = H - MB - h;
  return (
    <g pointerEvents="none">
      <rect x={tx} y={ty} width={w} height={h} rx={6} fill="#0b1326" stroke={C.grid} />
      {linhas.map((l, i) => (
        <text key={i} x={tx + 8} y={ty + 15 + i * 15} fontSize={11} fill={C.txt}>{l}</text>
      ))}
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
