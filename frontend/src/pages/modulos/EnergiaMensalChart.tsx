import { useMemo, useState } from "react";
import { fmt, MESES } from "./loadUtils";
import { C, niceCeil } from "./chartTheme";

const W = 980, H = 300, ML = 64, MR = 64, MT = 24, MB = 52;
const PW = W - ML - MR, PH = H - MT - MB;

interface Props {
  ponta: number[]; // 12
  fp: number[]; // 12
}

/** Energia mensal (kWh) como barras empilhadas Ponta + Fora-ponta (tema Aurova). */
export function EnergiaMensalChart({ ponta, fp }: Props) {
  const [hover, setHover] = useState<number | null>(null);

  const calc = useMemo(() => {
    const total = MESES.map((_, i) => (ponta[i] ?? 0) + (fp[i] ?? 0));
    const totPonta = ponta.reduce((a, b) => a + b, 0);
    const totFp = fp.reduce((a, b) => a + b, 0);
    const media = total.reduce((a, b) => a + b, 0) / 12;
    const yMax = niceCeil(Math.max(1, ...total));
    return { total, totPonta, totFp, media, yMax };
  }, [ponta, fp]);

  const { total, totPonta, totFp, media, yMax } = calc;
  const y = (v: number) => MT + PH - (v / yMax) * PH;
  const ticks = Array.from({ length: 5 }, (_, i) => (yMax / 4) * i);
  const band = PW / 12;
  const bw = band * 0.6;
  const cx = (i: number) => ML + band * (i + 0.5);
  const sel = hover;

  return (
    <section className="painel">
      <h3>Energia mensal — Ponta + Fora-ponta (kWh)</h3>
      <p className="muted" style={{ marginTop: -6 }}>
        Total: {fmt(totPonta + totFp)} kWh · Ponta: {fmt(totPonta)} kWh · Fora-ponta: {fmt(totFp)} kWh
        {" · "}média/mês {fmt(media)} kWh
        {sel != null && ` · ${MESES[sel]}: ${fmt(total[sel])} kWh (P ${fmt(ponta[sel])} · FP ${fmt(fp[sel])})`}
      </p>

      {/* Legenda */}
      <div style={{ display: "flex", gap: 16, fontSize: 13, color: C.txt, margin: "2px 0 8px" }}>
        <Swatch cor={C.foraPonta} rotulo="Fora-ponta" />
        <Swatch cor={C.ponta} rotulo="Ponta" />
        <span style={{ color: C.media }}>— — média/mês</span>
      </div>

      <div style={{ background: C.painel, borderRadius: 10, padding: "8px 4px" }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}
          onMouseLeave={() => setHover(null)}>
          {/* Grade + eixo Y */}
          {ticks.map((t) => (
            <g key={t}>
              <line x1={ML} y1={y(t)} x2={ML + PW} y2={y(t)} stroke={C.grid} strokeWidth={1} strokeDasharray="1 4" />
              <text x={ML - 10} y={y(t) - 1} textAnchor="end" fontSize={12} fill={C.txt}>{fmt(t)}</text>
              <text x={ML - 10} y={y(t) + 12} textAnchor="end" fontSize={10} fill={C.muted}>kWh</text>
            </g>
          ))}

          {/* Barras empilhadas */}
          {MESES.map((mes, i) => {
            const baseY = MT + PH;
            const fpTop = y(fp[i] ?? 0);
            const pontaTop = y((fp[i] ?? 0) + (ponta[i] ?? 0));
            const op = sel == null || sel === i ? 1 : 0.45;
            return (
              <g key={mes} onMouseEnter={() => setHover(i)} style={{ cursor: "pointer" }}>
                <rect x={cx(i) - band / 2} y={MT} width={band} height={PH} fill="transparent" />
                <rect x={cx(i) - bw / 2} y={fpTop} width={bw} height={Math.max(0, baseY - fpTop)}
                  fill={C.foraPonta} opacity={op} rx={1.5} />
                <rect x={cx(i) - bw / 2} y={pontaTop} width={bw} height={Math.max(0, fpTop - pontaTop)}
                  fill={C.ponta} opacity={op} rx={1.5} />
                <text x={cx(i)} y={MT + PH + 18} textAnchor="middle" fontSize={12} fill={C.txt}>{mes}</text>
              </g>
            );
          })}

          {/* Média (âmbar tracejada) */}
          <line x1={ML} y1={y(media)} x2={ML + PW} y2={y(media)} stroke={C.media} strokeWidth={1.6} strokeDasharray="7 5" />
          <text x={ML + PW + 6} y={y(media) + 4} fontSize={12} fill={C.media}>Média</text>

          <text x={ML + PW / 2} y={H - 10} textAnchor="middle" fontSize={13} fill={C.txt}>Mês</text>
        </svg>
      </div>
    </section>
  );
}

function Swatch({ cor, rotulo }: { cor: string; rotulo: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 12, height: 12, background: cor, borderRadius: 3, display: "inline-block" }} />
      {rotulo}
    </span>
  );
}
