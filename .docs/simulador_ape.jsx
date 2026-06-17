import { useState, useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar, ResponsiveContainer } from "recharts";

const fmt = (v, decimals = 0) =>
  v == null || isNaN(v) ? "-" : v.toLocaleString("pt-BR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const pct = (v) => (v == null || isNaN(v) ? "-" : (v * 100).toFixed(1) + "%");

const ANOS = Array.from({ length: 30 }, (_, i) => 2021 + i);

export default function SimuladorAPE() {
  const [tab, setTab] = useState("inputs");

  // ── INPUTS ──────────────────────────────────────────────────────────────
  const [potKwp, setPotKwp] = useState(4379);
  const [potKw, setPotKw] = useState(3190);
  const [yield_, setYield] = useState(112.04); // kWh/kWp/mês
  const [degradacao, setDegradacao] = useState(0.0055); // % ao ano
  const [consumoHFP, setConsumoHFP] = useState(23896); // MWh/ano
  const [consumoHP, setConsumoHP] = useState(1857);

  const [tusdHFP, setTusdHFP] = useState(397.32); // BRL/MWh
  const [teHFP, setTeHFP] = useState(270.9); // BRL/MWh
  const [tusdFioHFP, setTusdFioHFP] = useState(23.2); // BRL/kW
  const [tusdg, setTusdg] = useState(7.31); // BRL/kW

  const [ofertaBOT, setOfertaBOT] = useState(300); // BRL/MWh
  const [pctAluguel, setPctAluguel] = useState(0.85);
  const [periodoContrato, setPeriodoContrato] = useState(20);

  const [icms, setIcms] = useState(0.18);
  const [pisCofins, setPisCofins] = useState(0.055);
  const [creditaICMS, setCreditaICMS] = useState(false); // false = não credita (=1 na planilha)
  const [creditaPisCofins, setCreditaPisCofins] = useState(false);

  const [ipca, setIpca] = useState(0.03524);
  const [spread, setSpread] = useState(0.065);
  const [periodoMudancaReg, setPeriodoMudancaReg] = useState(15);
  const [fioBTUSD, setFioBTUSD] = useState(0.28);

  // Derived
  const pctOM = 1 - pctAluguel;
  const aluguelUFV = ofertaBOT * pctAluguel;
  const om = ofertaBOT * pctOM;
  const taxaDesconto = (1 + ipca) * (1 + spread) - 1;

  // ── CÁLCULOS ─────────────────────────────────────────────────────────────
  const results = useMemo(() => {
    const geracaoAno1 = potKwp * yield_ * 12 / 1000; // MWh/ano

    // Indexação IPCA acumulada (base = 1 no ano 1)
    const idxIPCA = ANOS.map((_, i) => Math.pow(1 + ipca, i));

    // Geração de energia por ano (MWh)
    const geracao = ANOS.map((_, i) => {
      if (i === 0) return geracaoAno1;
      return geracaoAno1 * Math.pow(1 - degradacao, i);
    });

    // Consumo monômio
    const consumoTotal = consumoHFP + consumoHP;

    // Balanço: energia consumida da rede (ACR) = consumo total - geração
    const balAcr = ANOS.map((_, i) => consumoTotal - geracao[i]);

    // Tarifas reajustadas
    const tusdHFPt = ANOS.map((_, i) => tusdHFP * idxIPCA[i]);
    const teHFPt = ANOS.map((_, i) => teHFP * idxIPCA[i]);
    const tusdFioHFPt = ANOS.map((_, i) => tusdFioHFP * idxIPCA[i]);
    const tusdgT = ANOS.map((_, i) => tusdg * idxIPCA[i]);

    // ── CUSTO ACR (sem GD) ──────────────────────────────────────
    const custoEnergiaACR = ANOS.map((_, i) => (teHFPt[i] * consumoTotal) / 1000);
    const custoEncargosACR = ANOS.map((_, i) => (tusdHFPt[i] * consumoTotal) / 1000);

    // Tributos ACR (quando não credita ICMS nem PIS/COFINS)
    const baseICMS_ACR = ANOS.map((_, i) => (custoEnergiaACR[i] + custoEncargosACR[i]) * icms / (1 - icms - pisCofins));
    const basePisCofins_ACR = ANOS.map((_, i) => (custoEnergiaACR[i] + custoEncargosACR[i]) * pisCofins / (1 - icms - pisCofins));
    const custoTributosACR = ANOS.map((_, i) => baseICMS_ACR[i] + basePisCofins_ACR[i]);

    // Demanda ACR (TUSD fio × potência instalada)
    const custoDemandaACR = ANOS.map((_, i) => (tusdFioHFPt[i] * potKw) / 1000);

    const custoACR = ANOS.map((_, i) =>
      custoEnergiaACR[i] + custoEncargosACR[i] + custoTributosACR[i] + custoDemandaACR[i]
    );

    // ── CUSTO GD / APE ──────────────────────────────────────────
    // Energia adquirida da rede = balanço (consumo - geração)
    const custoEnergiaAPE = ANOS.map((_, i) => (teHFPt[i] * balAcr[i]) / 1000);
    const custoEncargosAPE = ANOS.map((_, i) => (tusdHFPt[i] * balAcr[i]) / 1000);

    // Tributos APE
    const fatorTrib = icms + pisCofins;
    const custoICMS_APE = creditaICMS
      ? ANOS.map(() => 0)
      : ANOS.map((_, i) => (custoEnergiaAPE[i] + custoEncargosAPE[i]) * icms / (1 - fatorTrib));
    const custoPC_APE = creditaPisCofins
      ? ANOS.map(() => 0)
      : ANOS.map((_, i) => (custoEnergiaAPE[i] + custoEncargosAPE[i]) * pisCofins / (1 - fatorTrib));
    const custoTributosAPE = ANOS.map((_, i) => custoICMS_APE[i] + custoPC_APE[i]);

    // Demanda UFV (TUSDfio × kW instalado, apenas durante contrato)
    const custoDemandaAPE = ANOS.map((_, i) => {
      if (i < periodoMudancaReg) return (tusdFioHFPt[i] * potKw) / 1000;
      return (tusdgT[i] * potKw) / 1000; // após mudança reg.: TUSDg
    });

    // Investimento BOT (aluguel da usina) – apenas no período do contrato
    const investBOT = ANOS.map((_, i) => {
      if (i >= periodoContrato) return 0;
      return (aluguelUFV * geracao[i] * idxIPCA[i]) / 1000;
    });

    const custoAPE = ANOS.map((_, i) =>
      custoEnergiaAPE[i] + custoEncargosAPE[i] + custoTributosAPE[i] + custoDemandaAPE[i] + investBOT[i]
    );

    // ── CUSTO ACL (migração p/ livre, sem GD) ──────────────────
    // Simplificado: paga apenas TE + PIS/COFINS + demanda (sem ICMS por incentivo)
    // O modelo usa Desc TUSD ACL = 0 (sem desconto)
    const custoEnergiaACL = ANOS.map((_, i) => (teHFPt[i] * consumoTotal) / 1000 * (1 - pisCofins));
    const custoEncargosACL = ANOS.map((_, i) => (tusdHFPt[i] * consumoTotal) / 1000 * 0.5); // aproximação
    const custoDemandaACL = ANOS.map((_, i) => (tusdFioHFPt[i] * potKw) / 1000);
    const custoTributosACL = ANOS.map((_, i) => (custoEnergiaACL[i] + custoEncargosACL[i]) * pisCofins / (1 - pisCofins));
    const custoACL = ANOS.map((_, i) =>
      custoEnergiaACL[i] + custoEncargosACL[i] + custoDemandaACL[i] + custoTributosACL[i]
    );

    // ── ECONOMIAS ───────────────────────────────────────────────
    const econAPEvACR = ANOS.map((_, i) => custoACR[i] - custoAPE[i]);
    const econACLvACR = ANOS.map((_, i) => custoACR[i] - custoACL[i]);

    // ── NPV ─────────────────────────────────────────────────────
    const npv = (fluxos) =>
      fluxos.reduce((acc, v, i) => acc + v / Math.pow(1 + taxaDesconto, i + 1), 0);

    const npvACR = npv(custoACR);
    const npvAPE = npv(custoAPE);
    const npvACL = npv(custoACL);
    const npvEconAPE = npv(econAPEvACR);
    const npvEconACL = npv(econACLvACR);

    // ── PAYBACK ─────────────────────────────────────────────────
    let econAcumAPE = 0;
    let paybackAPE = null;
    let econAcumACL = 0;
    let paybackACL = null;
    ANOS.forEach((_, i) => {
      econAcumAPE += econAPEvACR[i];
      econAcumACL += econACLvACR[i];
      if (econAcumAPE >= 0 && paybackAPE === null) paybackAPE = i + 1;
      if (econAcumACL >= 0 && paybackACL === null) paybackACL = i + 1;
    });

    // desconto percebido médio
    const descAPEvACR = ANOS.map((_, i) => (custoACR[i] > 0 ? econAPEvACR[i] / custoACR[i] : 0));
    const descACLvACR = ANOS.map((_, i) => (custoACR[i] > 0 ? econACLvACR[i] / custoACR[i] : 0));

    // % atendimento
    const pctAtendimento = geracaoAno1 / consumoTotal;

    return {
      ANOS, geracao, geracaoAno1, pctAtendimento,
      custoACR, custoAPE, custoACL,
      investBOT,
      custoEnergiaACR, custoEncargosACR, custoDemandaACR, custoTributosACR,
      custoEnergiaAPE, custoEncargosAPE, custoDemandaAPE, custoTributosAPE,
      econAPEvACR, econACLvACR,
      descAPEvACR, descACLvACR,
      npvACR, npvAPE, npvACL, npvEconAPE, npvEconACL,
      paybackAPE, paybackACL,
      taxaDesconto,
    };
  }, [
    potKwp, potKw, yield_, degradacao, consumoHFP, consumoHP,
    tusdHFP, teHFP, tusdFioHFP, tusdg, ofertaBOT, pctAluguel,
    periodoContrato, icms, pisCofins, creditaICMS, creditaPisCofins,
    ipca, spread, periodoMudancaReg, fioBTUSD,
  ]);

  const chartData = ANOS.map((ano, i) => ({
    ano,
    ACR: +(results.custoACR[i] / 1000).toFixed(2),
    APE: +(results.custoAPE[i] / 1000).toFixed(2),
    ACL: +(results.custoACL[i] / 1000).toFixed(2),
    EconAPE: +(results.econAPEvACR[i] / 1000).toFixed(2),
    EconACL: +(results.econACLvACR[i] / 1000).toFixed(2),
  }));

  const tabs = ["inputs", "resultados", "custos", "economia", "geração"];

  return (
    <div style={{ fontFamily: "Arial, sans-serif", fontSize: 13, background: "#f5f7fa", minHeight: "100vh", padding: 16 }}>
      {/* Header */}
      <div style={{ background: "#1a3a5c", color: "#fff", padding: "12px 20px", borderRadius: 8, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Simulador APE – GD Solar</div>
          <div style={{ fontSize: 11, opacity: 0.8 }}>Motor de análise | ACR vs APE vs ACL</div>
        </div>
        <div style={{ textAlign: "right", fontSize: 12 }}>
          <div>Geração Ano 1: <b>{fmt(results.geracaoAno1, 0)} MWh/ano</b></div>
          <div>Atendimento: <b>{pct(results.pctAtendimento)}</b></div>
          <div>Taxa Desconto: <b>{pct(results.taxaDesconto)}</b></div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: "6px 14px", border: "none", borderRadius: 6, cursor: "pointer",
            background: tab === t ? "#1a3a5c" : "#dce3ec", color: tab === t ? "#fff" : "#333",
            fontWeight: tab === t ? 700 : 400, fontSize: 12, textTransform: "capitalize"
          }}>{t}</button>
        ))}
      </div>

      {/* ── INPUTS ── */}
      {tab === "inputs" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <Card title="Dados da UFV">
            <Field label="Potência (kWp)" val={potKwp} set={setPotKwp} />
            <Field label="Potência (kW)" val={potKw} set={setPotKw} />
            <Field label="Yield (kWh/kWp/mês)" val={yield_} set={setYield} step={0.1} />
            <Field label="Degradação (% a.a.)" val={degradacao * 100} set={v => setDegradacao(v / 100)} step={0.01} />
          </Card>
          <Card title="Consumo do Cliente">
            <Field label="Consumo HFP (MWh/ano)" val={consumoHFP} set={setConsumoHFP} />
            <Field label="Consumo HP (MWh/ano)" val={consumoHP} set={setConsumoHP} />
          </Card>
          <Card title="Oferta BOT">
            <Field label="Valor da Oferta (BRL/MWh)" val={ofertaBOT} set={setOfertaBOT} />
            <Field label="% Aluguel" val={pctAluguel * 100} set={v => setPctAluguel(v / 100)} step={1} />
            <Field label="Período Contrato BOT (anos)" val={periodoContrato} set={setPeriodoContrato} />
            <div style={{ background: "#eef4ff", borderRadius: 4, padding: "6px 8px", marginTop: 8, fontSize: 11 }}>
              <div>Aluguel: <b>{fmt(aluguelUFV, 2)} BRL/MWh</b></div>
              <div>O&M: <b>{fmt(om, 2)} BRL/MWh</b></div>
            </div>
          </Card>
          <Card title="Tarifas Distribuidora">
            <Field label="TUSD HFP (BRL/MWh)" val={tusdHFP} set={setTusdHFP} step={0.1} />
            <Field label="TE HFP (BRL/MWh)" val={teHFP} set={setTeHFP} step={0.1} />
            <Field label="TUSDfio HFP (BRL/kW)" val={tusdFioHFP} set={setTusdFioHFP} step={0.1} />
            <Field label="TUSDg (BRL/kW)" val={tusdg} set={setTusdg} step={0.01} />
          </Card>
          <Card title="Tributos">
            <Field label="ICMS (%)" val={icms * 100} set={v => setIcms(v / 100)} step={0.1} />
            <Field label="PIS/COFINS (%)" val={pisCofins * 100} set={v => setPisCofins(v / 100)} step={0.1} />
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
              <input type="checkbox" checked={creditaICMS} onChange={e => setCreditaICMS(e.target.checked)} />
              Credita ICMS?
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
              <input type="checkbox" checked={creditaPisCofins} onChange={e => setCreditaPisCofins(e.target.checked)} />
              Credita PIS/COFINS?
            </label>
          </Card>
          <Card title="Macroeconômico">
            <Field label="IPCA (% a.a.)" val={ipca * 100} set={v => setIpca(v / 100)} step={0.1} />
            <Field label="Spread (% a.a.)" val={spread * 100} set={v => setSpread(v / 100)} step={0.1} />
            <Field label="Período mudança regulatória (anos)" val={periodoMudancaReg} set={setPeriodoMudancaReg} />
            <Field label="Fio B TUSD encargo (%)" val={fioBTUSD * 100} set={v => setFioBTUSD(v / 100)} step={1} />
          </Card>
        </div>
      )}

      {/* ── RESULTADOS ── */}
      {tab === "resultados" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
            <KPI label="NPV ACR (30 anos)" val={"BRL " + fmt(results.npvACR / 1000, 0) + " M"} color="#c0392b" />
            <KPI label="NPV APE (30 anos)" val={"BRL " + fmt(results.npvAPE / 1000, 0) + " M"} color="#27ae60" />
            <KPI label="NPV ACL (30 anos)" val={"BRL " + fmt(results.npvACL / 1000, 0) + " M"} color="#2980b9" />
            <KPI label="NPV Economia APE vs ACR" val={"BRL " + fmt(results.npvEconAPE / 1000, 0) + " M"} color="#27ae60" />
            <KPI label="Desconto APE vs ACR (NPV)" val={pct(results.npvEconAPE / results.npvACR)} color="#27ae60" />
            <KPI label="% Atendimento" val={pct(results.pctAtendimento)} color="#8e44ad" />
          </div>
          <Card title="Custo Anual Comparativo (BRL MM)">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="ano" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={v => v.toFixed(1)} />
                <Tooltip formatter={(v, n) => ["BRL " + v.toFixed(2) + " MM", n]} />
                <Legend />
                <Line type="monotone" dataKey="ACR" stroke="#c0392b" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="APE" stroke="#27ae60" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="ACL" stroke="#2980b9" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}

      {/* ── CUSTOS ── */}
      {tab === "custos" && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 11 }}>
            <thead>
              <tr style={{ background: "#1a3a5c", color: "#fff" }}>
                <th style={th}>Ano</th>
                <th style={th}>ACR (BRL M)</th>
                <th style={{ ...th, color: "#a8d8a8" }}>APE (BRL M)</th>
                <th style={{ ...th, color: "#a8c8f8" }}>ACL (BRL M)</th>
                <th style={th}>Geração (MWh)</th>
                <th style={th}>Inv. BOT (BRL M)</th>
              </tr>
            </thead>
            <tbody>
              {ANOS.map((ano, i) => (
                <tr key={ano} style={{ background: i % 2 === 0 ? "#fff" : "#f5f7fa" }}>
                  <td style={td}>{ano}</td>
                  <td style={{ ...td, color: "#c0392b", fontWeight: 600 }}>{fmt(results.custoACR[i] / 1000, 2)}</td>
                  <td style={{ ...td, color: "#27ae60", fontWeight: 600 }}>{fmt(results.custoAPE[i] / 1000, 2)}</td>
                  <td style={{ ...td, color: "#2980b9", fontWeight: 600 }}>{fmt(results.custoACL[i] / 1000, 2)}</td>
                  <td style={td}>{fmt(results.geracao[i], 0)}</td>
                  <td style={td}>{fmt(results.investBOT[i] / 1000, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── ECONOMIA ── */}
      {tab === "economia" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
            <KPI label="Payback Simples APE" val={results.paybackAPE ? results.paybackAPE + " anos" : "N/A"} color="#27ae60" />
            <KPI label="Payback Simples ACL" val={results.paybackACL ? results.paybackACL + " anos" : "N/A"} color="#2980b9" />
          </div>
          <Card title="Economia Anual: APE vs ACR & ACL vs ACR (BRL MM)">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="ano" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(1)} />
                <Tooltip formatter={(v, n) => ["BRL " + v.toFixed(2) + " MM", n]} />
                <Legend />
                <Bar dataKey="EconAPE" name="Econ APE vs ACR" fill="#27ae60" />
                <Bar dataKey="EconACL" name="Econ ACL vs ACR" fill="#2980b9" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <div style={{ overflowX: "auto", marginTop: 12 }}>
            <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 11 }}>
              <thead>
                <tr style={{ background: "#1a3a5c", color: "#fff" }}>
                  <th style={th}>Ano</th>
                  <th style={th}>Econ APE vs ACR (BRL M)</th>
                  <th style={th}>Desc APE vs ACR (%)</th>
                  <th style={th}>Econ ACL vs ACR (BRL M)</th>
                  <th style={th}>Desc ACL vs ACR (%)</th>
                </tr>
              </thead>
              <tbody>
                {ANOS.map((ano, i) => (
                  <tr key={ano} style={{ background: i % 2 === 0 ? "#fff" : "#f5f7fa" }}>
                    <td style={td}>{ano}</td>
                    <td style={{ ...td, color: results.econAPEvACR[i] >= 0 ? "#27ae60" : "#c0392b", fontWeight: 600 }}>
                      {fmt(results.econAPEvACR[i] / 1000, 2)}
                    </td>
                    <td style={td}>{pct(results.descAPEvACR[i])}</td>
                    <td style={{ ...td, color: results.econACLvACR[i] >= 0 ? "#27ae60" : "#c0392b", fontWeight: 600 }}>
                      {fmt(results.econACLvACR[i] / 1000, 2)}
                    </td>
                    <td style={td}>{pct(results.descACLvACR[i])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── GERAÇÃO ── */}
      {tab === "geração" && (
        <div>
          <Card title="Geração Anual vs Consumo (MWh)">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart
                data={ANOS.map((ano, i) => ({
                  ano,
                  Geração: +results.geracao[i].toFixed(0),
                  "Consumo Total": consumoHFP + consumoHP,
                  "Saldo (ACR)": +results.balAcr?.[i]?.toFixed(0) ?? 0,
                }))}
                margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="ano" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="Geração" stroke="#f39c12" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Consumo Total" stroke="#7f8c8d" strokeWidth={1} strokeDasharray="5 5" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function Card({ title, children }) {
  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.1)" }}>
      <div style={{ fontWeight: 700, color: "#1a3a5c", marginBottom: 12, borderBottom: "2px solid #e0e8f0", paddingBottom: 6 }}>{title}</div>
      {children}
    </div>
  );
}

function KPI({ label, val, color }) {
  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.1)", textAlign: "center" }}>
      <div style={{ fontSize: 11, color: "#666", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{val}</div>
    </div>
  );
}

function Field({ label, val, set, step = 1 }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 11, color: "#555", display: "block", marginBottom: 2 }}>{label}</label>
      <input
        type="number"
        value={val}
        step={step}
        onChange={e => set(parseFloat(e.target.value) || 0)}
        style={{ width: "100%", padding: "4px 8px", border: "1px solid #ccd", borderRadius: 4, fontSize: 12 }}
      />
    </div>
  );
}

const th = { padding: "6px 10px", textAlign: "right", whiteSpace: "nowrap", fontWeight: 600, fontSize: 11 };
const td = { padding: "4px 10px", textAlign: "right", borderBottom: "1px solid #eee" };
