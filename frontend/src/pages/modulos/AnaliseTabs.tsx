import { useMemo, useState } from "react";
import type { DiaDemanda, FPInfo } from "../../types";
import { fmt, MESES } from "./loadUtils";
import { C, niceCeil } from "./chartTheme";
import { indicadores, pqsPorHora } from "./loadAnalise";
import { CosphiDiarioChart, DemandaDiariaChart } from "./DemandaDiariaChart";

const W = 980, ML = 58, MR = 20, MT = 20, MB = 44, PW = W - ML - MR;

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

// ════════════════════════════════════════════════════════════════════════════
// ABA P · Q · S
// ════════════════════════════════════════════════════════════════════════════
export function AbaPQS({ curva24, fp, setFp, fpReal, serie, fonte }: {
  curva24: number[]; fp: number; setFp: (v: number) => void; fpReal?: FPInfo | null;
  serie: DiaDemanda[]; fonte: string;
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

  const horasCap = linhas.filter((l) => l.cap).length;

  // Timeline compartilhada: hover/slider em qualquer gráfico move o dia em todos.
  const defaultDia = useMemo(() => {
    let iP = 0;
    serie.forEach((d, i) => { if (serie[iP] && d.total_kwh > serie[iP].total_kwh) iP = i; });
    return iP;
  }, [serie]);
  const [hoverDia, setHoverDia] = useState<number | null>(null);
  const [pinDia, setPinDia] = useState<number | null>(null);
  const selDia = hoverDia ?? pinDia ?? defaultDia;

  return (
    <>
      <DemandaDiariaChart serie={serie} fonte={fonte} fp={real ? real.medio : fp}
        selIndex={selDia} onHoverIndex={setHoverDia} onPinIndex={setPinDia} />

      <CosphiDiarioChart serie={serie} fpNom={real ? real.medio : fp} fonte={fonte}
        selIndex={selDia} onHoverIndex={setHoverDia} onPinIndex={setPinDia} />

      <section className="painel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <h3 style={{ margin: 0 }}>Fator de potência (cosφ)</h3>
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
