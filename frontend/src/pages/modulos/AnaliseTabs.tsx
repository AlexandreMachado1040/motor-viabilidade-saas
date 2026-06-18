import { useMemo, useRef, useState } from "react";
import type { FPInfo } from "../../types";
import { fmt, MESES } from "./loadUtils";
import { C, niceCeil } from "./chartTheme";
import { ALFA_FP, indicadores, pqsPorHora } from "./loadAnalise";

const W = 980, ML = 58, MR = 20, MT = 20, MB = 44, PW = W - ML - MR;

interface XTick { i: number; label: string; }
interface Serie { nome: string; cor: string; dados: number[]; tracejado?: boolean; area?: boolean; }

// ── Gráfico de linhas/área genérico (SVG, tema Aurova) com crosshair ─────────
function GraficoLinhas({ H, series, xTicks, yMin = 0, yMax, unidade, decTick = 0, decVal = 1, rotuloX }: {
  H: number; series: Serie[]; xTicks: XTick[]; yMin?: number; yMax: number; unidade: string;
  decTick?: number; decVal?: number; rotuloX?: (i: number) => string;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [hi, setHi] = useState<number | null>(null);
  const PH = H - MT - MB;
  const n = series[0]?.dados.length ?? 0;
  const x = (i: number) => (n <= 1 ? ML : ML + (i / (n - 1)) * PW);
  const y = (v: number) => MT + PH - ((v - yMin) / (yMax - yMin)) * PH;
  const ticks = Array.from({ length: 5 }, (_, i) => yMin + ((yMax - yMin) / 4) * i);

  const aoMover = (e: React.MouseEvent) => {
    const svg = ref.current; if (!svg || n <= 1) return;
    const r = svg.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * W;
    const i = Math.round(((mx - ML) / PW) * (n - 1));
    setHi(Math.max(0, Math.min(n - 1, i)));
  };

  return (
    <div style={{ background: C.painel, borderRadius: 10, padding: "8px 4px" }}>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}
        onMouseMove={aoMover} onMouseLeave={() => setHi(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={ML} y1={y(t)} x2={ML + PW} y2={y(t)} stroke={C.grid} strokeWidth={1} strokeDasharray="1 4" />
            <text x={ML - 8} y={y(t) - 1} textAnchor="end" fontSize={11} fill={C.txt}>{fmt(t, decTick)}</text>
          </g>
        ))}
        <text x={ML - 8} y={MT - 4} textAnchor="end" fontSize={9} fill={C.muted}>{unidade}</text>
        {xTicks.map((xt) => (
          <text key={xt.i} x={x(xt.i)} y={MT + PH + 16} textAnchor="middle" fontSize={10} fill={C.txt}>{xt.label}</text>
        ))}
        {series.map((s) => {
          const d = "M" + s.dados.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" L");
          return (
            <g key={s.nome}>
              {s.area && <path d={`${d} L${x(n - 1).toFixed(1)},${MT + PH} L${x(0).toFixed(1)},${MT + PH} Z`} fill={s.cor + "22"} />}
              <path d={d} fill="none" stroke={s.cor} strokeWidth={2} strokeDasharray={s.tracejado ? "6 4" : undefined} strokeLinejoin="round" />
            </g>
          );
        })}
        {hi != null && (
          <>
            <line x1={x(hi)} y1={MT} x2={x(hi)} y2={MT + PH} stroke={C.cursor} strokeWidth={1.2} />
            {series.map((s) => (
              <circle key={s.nome} cx={x(hi)} cy={y(s.dados[hi])} r={3.2} fill={s.cor} stroke={C.bg} strokeWidth={1.2} />
            ))}
            <TipLinhas xc={x(hi)} titulo={rotuloX ? rotuloX(hi) : String(hi)}
              itens={series.map((s) => ({ nome: s.nome, cor: s.cor, val: fmt(s.dados[hi], decVal) }))} />
          </>
        )}
      </svg>
      <Legenda series={series} />
    </div>
  );
}

function TipLinhas({ xc, titulo, itens }: { xc: number; titulo: string; itens: { nome: string; cor: string; val: string }[] }) {
  const larg = Math.max(titulo.length, ...itens.map((i) => i.nome.length + i.val.length + 3)) * 6.2 + 22;
  const alt = 16 + itens.length * 14 + 6;
  let tx = xc + 12; if (tx + larg > ML + PW) tx = xc - larg - 12; if (tx < ML) tx = ML;
  const ty = MT + 4;
  return (
    <g pointerEvents="none">
      <rect x={tx} y={ty} width={larg} height={alt} rx={6} fill="#0b1326" stroke={C.grid} />
      <text x={tx + 8} y={ty + 14} fontSize={11} fill={C.txt} fontWeight={700}>{titulo}</text>
      {itens.map((it, i) => (
        <g key={it.nome}>
          <rect x={tx + 8} y={ty + 20 + i * 14} width={9} height={9} rx={2} fill={it.cor} />
          <text x={tx + 21} y={ty + 28 + i * 14} fontSize={10} fill={C.muted}>{it.nome}</text>
          <text x={tx + larg - 8} y={ty + 28 + i * 14} fontSize={10} fill={C.txt} textAnchor="end">{it.val}</text>
        </g>
      ))}
    </g>
  );
}

function GraficoBarras({ H, valores, labels, cor, unidade, destaque }: {
  H: number; valores: number[]; labels: string[]; cor: string; unidade: string; destaque?: number;
}) {
  const PH = H - MT - MB;
  const yMax = niceCeil(Math.max(1, ...valores));
  const y = (v: number) => MT + PH - (v / yMax) * PH;
  const band = PW / valores.length;
  const bw = band * 0.6;
  const cx = (i: number) => ML + band * (i + 0.5);
  const ticks = Array.from({ length: 5 }, (_, i) => (yMax / 4) * i);
  return (
    <div style={{ background: C.painel, borderRadius: 10, padding: "8px 4px" }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={ML} y1={y(t)} x2={ML + PW} y2={y(t)} stroke={C.grid} strokeWidth={1} strokeDasharray="1 4" />
            <text x={ML - 8} y={y(t) - 1} textAnchor="end" fontSize={11} fill={C.txt}>{fmt(t)}</text>
          </g>
        ))}
        <text x={ML - 8} y={MT - 4} textAnchor="end" fontSize={9} fill={C.muted}>{unidade}</text>
        {valores.map((v, i) => (
          <g key={i}>
            <rect x={cx(i) - bw / 2} y={y(v)} width={bw} height={Math.max(0, MT + PH - y(v))}
              fill={cor} opacity={destaque == null || destaque === i ? 0.9 : 0.4} rx={2} />
            {labels.length <= 24 && <text x={cx(i)} y={MT + PH + 15} textAnchor="middle" fontSize={9} fill={C.txt}>{labels[i]}</text>}
          </g>
        ))}
      </svg>
    </div>
  );
}

function Legenda({ series }: { series: Serie[] }) {
  return (
    <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: 12, color: C.txt, padding: "6px 8px 0" }}>
      {series.map((s) => (
        <span key={s.nome} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 14, height: 3, background: s.cor, display: "inline-block" }} />{s.nome}
        </span>
      ))}
    </div>
  );
}

const horasTicks: XTick[] = Array.from({ length: 24 }, (_, h) => h).filter((h) => h % 2 === 0).map((h) => ({ i: h, label: `${h}h` }));

// ════════════════════════════════════════════════════════════════════════════
// ABA P · Q · S
// ════════════════════════════════════════════════════════════════════════════
export function AbaPQS({ curva24, fp, setFp, fpReal }: {
  curva24: number[]; fp: number; setFp: (v: number) => void; fpReal?: FPInfo | null;
}) {
  const real = fpReal ?? null;

  const linhas = useMemo(() => {
    if (real) {
      const dmaxR = Math.max(1e-9, ...real.pPorHora);
      return real.pPorHora.map((p, h) => {
        const q = real.qPorHora[h], fph = real.fpPorHora[h];
        return {
          hora: h, p: +p.toFixed(3), q: +q.toFixed(3), s: +Math.hypot(p, q).toFixed(3),
          fpParcial: fph, phi: +(Math.acos(Math.min(1, fph)) * 180 / Math.PI).toFixed(2),
          norm: +(p / dmaxR).toFixed(4), cap: real.capPorHora[h],
        };
      });
    }
    return pqsPorHora(curva24, fp).map((l) => ({ ...l, cap: false }));
  }, [real, curva24, fp]);

  const dmax = Math.max(1, ...linhas.map((l) => l.p));
  const yMax = niceCeil(Math.max(1, ...linhas.map((l) => l.s)));
  const horasCap = linhas.filter((l) => l.cap).length;

  return (
    <>
      <section className="painel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <h3 style={{ margin: 0 }}>Triângulo de potências — P · Q · S por hora</h3>
          {real ? (
            <span style={{ fontSize: 12, color: C.muted }}>
              FP real medido ({real.fonte}) · médio <strong style={{ color: real.medio < 0.92 ? C.red : C.acc }}>{real.medio.toFixed(4)}</strong>
              {" · "}ponta {real.ponta.toFixed(4)} · fora {real.fora.toFixed(4)}
            </span>
          ) : (
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: C.muted }}>
              Fator de potência (cosφ): <strong style={{ color: fp < 0.92 ? C.red : C.acc }}>{fp.toFixed(2)}</strong>
              <input type="range" min={0.7} max={1} step={0.01} value={fp}
                onChange={(e) => setFp(Number(e.target.value))} style={{ accentColor: C.acc as string }} />
            </label>
          )}
        </div>
        {real && real.medio < 0.92 && <div style={{ color: C.red, fontSize: 11, marginTop: 4 }}>⚠ FP médio abaixo de 0,92 — sujeito a excedente de reativo (ANEEL).</div>}
        {real && horasCap > 0 && <div style={{ color: C.media, fontSize: 11, marginTop: 4 }}>↯ {horasCap} h com reativo capacitivo predominante (tipicamente carga baixa/madrugada) — risco de excedente capacitivo (OSE/Starosta).</div>}
        <div style={{ marginTop: 10 }}>
          <GraficoLinhas H={300} yMax={yMax} unidade="kVA / kVAr / kW" xTicks={horasTicks} decVal={1} rotuloX={(i) => `${i}h`} series={[
            { nome: "P ativa (kW)", cor: C.linha, dados: linhas.map((l) => l.p), area: true },
            { nome: "Q reativa (kVAr)", cor: C.media, dados: linhas.map((l) => l.q), tracejado: true },
            { nome: "S aparente (kVA)", cor: C.cursor, dados: linhas.map((l) => l.s) },
          ]} />
        </div>
      </section>

      <section className="painel">
        <h3>{real ? "Fator de potência medido por hora" : "FP em regime de carga baixa"}</h3>
        <p className="muted" style={{ marginTop: -6 }}>
          {real
            ? "FP por hora calculado da memória de massa: FP = P / √(P² + Q²). Abaixo de 0,92 (indutivo ou capacitivo) há excedente."
            : <>Em carga parcial o ângulo de fase cresce: <code style={{ color: C.media }}>FP_real ≈ FP_nom·(P/Dmáx)^{ALFA_FP}</code> (Starosta/OSE, partes I e II).</>}
        </p>
        <GraficoLinhas H={220} yMin={0.5} yMax={1.02} decTick={2} decVal={4} rotuloX={(i) => `${i}h`} unidade="cosφ" xTicks={horasTicks}
          series={real
            ? [
              { nome: "FP medido", cor: C.media, dados: linhas.map((l) => l.fpParcial) },
              { nome: "Limite ANEEL 0,92", cor: C.red, dados: linhas.map(() => 0.92), tracejado: true },
            ]
            : [
              { nome: "FP real (carga parcial)", cor: C.media, dados: linhas.map((l) => l.fpParcial) },
              { nome: "FP nominal", cor: C.linha, dados: linhas.map(() => fp), tracejado: true },
              { nome: "Limite ANEEL 0,92", cor: C.red, dados: linhas.map(() => 0.92), tracejado: true },
            ]} />
      </section>

      <section className="painel">
        <h3>Tabela horária — P · Q · S · FP</h3>
        <TabelaSimples
          cab={["Hora", "P (kW)", "Q (kVAr)", "S (kVA)", "FP", "φ (°)", "P p.u."]}
          linhas={linhas.map((l) => [
            `${String(l.hora).padStart(2, "0")}:00${l.cap ? " ↯" : ""}`,
            fmt(l.p, 1), fmt(l.q, 1), fmt(l.s, 1),
            { txt: l.fpParcial.toFixed(4), cor: l.fpParcial < 0.92 ? C.red : C.linha },
            l.phi.toFixed(1),
            { txt: (l.p / dmax).toFixed(3), cor: l.p === dmax ? C.acc : C.muted },
          ])} />
      </section>
    </>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// ABA FATORES
// ════════════════════════════════════════════════════════════════════════════
export function AbaFatores({ curva24, mensal, dInst, setDInst }: {
  curva24: number[]; mensal: number[]; dInst: number | null; setDInst: (v: number | null) => void;
}) {
  const dmaxCurva = useMemo(() => Math.max(0, ...curva24), [curva24]);
  const fdAuto = !(dInst && dInst > 0);
  const dInstEff = fdAuto ? Math.max(1, Math.round(dmaxCurva)) : dInst!;
  const ind = useMemo(() => indicadores(curva24, dInstEff), [curva24, dInstEff]);
  const fd = ind.fd ?? 1;
  const mesPico = mensal.indexOf(Math.max(...mensal));

  const cards = [
    { lbl: "FC — Fator de Carga", val: `${fmt(ind.fc * 100, 1)}%`, eq: "FC = Dméd / Dmáx", cor: C.linha, desc: "Aproveitamento médio; perto de 1 = uso eficiente." },
    { lbl: "FCV — Fator de Variação", val: `${fmt(ind.fcv * 100, 1)}%`, eq: "FCV = Dmin / Dmáx", cor: C.media, desc: "Amplitude de oscilação; baixo = grande variação." },
    { lbl: "Horas de Utilização", val: `${fmt(ind.hutil, 1)} h`, eq: "h_util = E / Dmáx", cor: C.cursor, desc: "Horas equivalentes a plena carga (máx. 24 h)." },
    { lbl: "FD — Fator de Demanda", val: `${fmt(fd * 100, 1)}%`, eq: "FD = Dmáx / D_inst", cor: C.acc, desc: fdAuto ? "D_inst = Dmáx (informe a instalada p/ ajustar)." : "Pico × potência instalada." },
  ];

  return (
    <>
      <section className="painel">
        <h3>Fatores da instalação (sobre a curva típica)</h3>
        <div className="grid-kpis">
          {cards.map((c) => (
            <div key={c.lbl} className="kpi" style={{ borderTop: `3px solid ${c.cor}` }}>
              <div className="kpi-titulo">{c.lbl}</div>
              <div className="kpi-valor" style={{ color: c.cor }}>{c.val}</div>
              <div style={{ fontSize: 10, color: C.media, fontFamily: "monospace", marginTop: 4 }}>{c.eq}</div>
              <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>{c.desc}</div>
            </div>
          ))}
        </div>
        <label className="campo" style={{ marginTop: 12 }}>
          <span>Demanda instalada D_inst (kW) — para o FD {fdAuto && <em style={{ color: C.muted }}>(vazio = Dmáx {fmt(dmaxCurva, 0)})</em>}</span>
          <input type="number" step="1" value={dInst ?? ""} placeholder={fmt(dmaxCurva, 0)}
            onChange={(e) => setDInst(e.target.value === "" ? null : Number(e.target.value))} />
        </label>
      </section>

      <section className="painel">
        <h3>Definição dos fatores</h3>
        <div>
          {[
            ["Fator de Carga (FC)", "FC = Dméd / Dmáx", `${fmt(ind.fc * 100, 1)}%`],
            ["Fator de Variação (FCV)", "FCV = Dmin / Dmáx", `${fmt(ind.fcv * 100, 1)}%`],
            ["Fator de Demanda (FD)", "FD = Dmáx / D_inst", `${fmt(fd * 100, 1)}%`],
            ["Horas de Utilização", "h_util = E / Dmáx", `${fmt(ind.hutil, 1)} h`],
            ["Energia diária", "E = Σ P(h)", `${fmt(ind.e24, 1)} kWh`],
            ["Demandas", "Dmáx · Dméd · Dmin", `${fmt(ind.dmax, 1)} · ${fmt(ind.dmed, 1)} · ${fmt(ind.dmin, 1)} kW`],
          ].map(([n, eq, val]) => (
            <div key={n} style={{ padding: "7px 0", borderBottom: `1px solid ${C.grid}` }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 12, color: C.txt, fontWeight: 600 }}>{n}</span>
                <span style={{ fontSize: 12, color: C.acc, fontFamily: "monospace" }}>{val}</span>
              </div>
              <div style={{ fontSize: 11, color: C.media, fontFamily: "monospace" }}>{eq}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="painel">
        <h3>Sazonalidade — energia mensal (kWh)</h3>
        <GraficoBarras H={220} valores={mensal} labels={MESES} cor={C.cursor} unidade="kWh" destaque={mesPico} />
      </section>
    </>
  );
}

// ── Tabela simples temática ──────────────────────────────────────────────────
type Cel = string | { txt: string; cor: string };
function TabelaSimples({ cab, linhas }: { cab: string[]; linhas: Cel[][] }) {
  const cor = (c: Cel) => (typeof c === "string" ? C.txt : c.cor);
  const txt = (c: Cel) => (typeof c === "string" ? c : c.txt);
  return (
    <div className="tabela-wrap" style={{ maxHeight: 360, overflow: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: "monospace" }}>
        <thead>
          <tr>{cab.map((c, i) => (
            <th key={c} style={{ textAlign: i === 0 ? "left" : "right", padding: "5px 8px", color: C.muted, borderBottom: `1px solid ${C.grid}`, position: "sticky", top: 0, background: C.painel }}>{c}</th>
          ))}</tr>
        </thead>
        <tbody>
          {linhas.map((lin, r) => (
            <tr key={r}>
              {lin.map((c, i) => (
                <td key={i} style={{ textAlign: i === 0 ? "left" : "right", padding: "3px 8px", color: cor(c), borderBottom: `1px solid ${C.grid}` }}>{txt(c)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
