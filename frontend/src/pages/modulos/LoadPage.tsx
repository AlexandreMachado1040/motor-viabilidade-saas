import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  fmt, matrizZerada, serieDiariaDeMatriz, vetorZerado,
} from "./loadUtils";
import { interpretar, lerPlanilha } from "./loadUpload";
import { DemandaDiariaChart } from "./DemandaDiariaChart";
import { EnergiaMensalChart } from "./EnergiaMensalChart";
import { BASES_CTR, carregarCampanha, listarDistribuidoras, listarOpcoes } from "./campanhaAneel";
import type { BaseId } from "./campanhaAneel";
import type { DiaDemanda } from "../../types";

export function LoadPage() {
  const [matriz, setMatriz] = useState<number[][]>(matrizZerada);
  const [ponta, setPonta] = useState<number[]>(vetorZerado);
  const [fp, setFp] = useState<number[]>(vetorZerado);
  const [demandaManual, setDemandaManual] = useState<number | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [avisoUpload, setAvisoUpload] = useState<string | null>(null);
  const [serieUpload, setSerieUpload] = useState<DiaDemanda[] | null>(null);
  const [fonteSerie, setFonteSerie] = useState<string | null>(null);

  // Campanha de Medição (curva-tipo ANEEL/CTR).
  const [campAberta, setCampAberta] = useState(false);
  const [base, setBase] = useState<BaseId>("rede");
  const [distribuidoras, setDistribuidoras] = useState<string[]>([]);
  const [sig, setSig] = useState("");
  const [subgrupos, setSubgrupos] = useState<string[]>([]);
  const [porSub, setPorSub] = useState<Record<string, string[]>>({});
  const [sbg, setSbg] = useState("");
  const [dem, setDem] = useState("");
  const demandantes = porSub[sbg] ?? [];

  // Série para o gráfico: real do arquivo/campanha (se houver) ou ano representativo da matriz.
  const serieGrafico = useMemo(
    () => serieUpload ?? serieDiariaDeMatriz(matriz),
    [serieUpload, matriz],
  );
  const fonteGrafico = serieUpload
    ? (fonteSerie ?? "memória de massa")
    : "perfil mensal replicado (representativo — sem leituras brutas)";

  // ── Derivados locais (preview imediato) ──────────────────────────────────
  const local = useMemo(() => {
    const picoGeral = Math.max(0, ...matriz.map((linha) => Math.max(0, ...linha)));
    return {
      demandaMaxima: demandaManual ?? picoGeral,
      pontaTotal: ponta.reduce((a, b) => a + b, 0),
      fpTotal: fp.reduce((a, b) => a + b, 0),
    };
  }, [matriz, ponta, fp, demandaManual]);

  const importarArquivo = async (file: File) => {
    setErro(null);
    setAvisoUpload(null);
    setCarregando(true);
    try {
      const rows = await lerPlanilha(file);
      const r = interpretar(rows);
      if (!r.ok || !r.payload) {
        setErro(r.aviso);
        return;
      }
      setMatriz(r.payload.demanda_kw);
      setPonta(r.payload.energia_ponta_kwh);
      setFp(r.payload.energia_fp_kwh);
      setDemandaManual(r.payload.demanda_maxima_kw);
      setSerieUpload(r.serieDiaria && r.serieDiaria.length > 0 ? r.serieDiaria : null);
      setFonteSerie("memória de massa (arquivo)");
      setAvisoUpload(r.aviso);
    } catch {
      setErro("Falha ao ler o arquivo. Verifique o formato/codificação.");
    } finally {
      setCarregando(false);
    }
  };

  // ── Campanha de Medição (curva-tipo ANEEL/CTR) ────────────────────────────
  // Carrega opções (subgrupos + demandantes) de uma distribuidora.
  const carregarOpcoesDist = async (b: BaseId, s: string) => {
    const { subgrupos: subs, porSub: mapa } = await listarOpcoes(b, s);
    setSubgrupos(subs); setPorSub(mapa);
    const sb0 = subs[0] ?? "";
    setSbg(sb0); setDem(mapa[sb0]?.[0] ?? "");
    if (subs.length === 0) setErro(`Sem curva-tipo para ${s} nesta base.`);
  };

  // Carrega distribuidoras da base e abre a 1ª.
  const carregarBase = async (b: BaseId) => {
    setErro(null); setCarregando(true);
    try {
      const dists = await listarDistribuidoras(b);
      setDistribuidoras(dists);
      const s0 = dists[0] ?? "";
      setSig(s0);
      if (s0) await carregarOpcoesDist(b, s0);
      else { setSubgrupos([]); setPorSub({}); setSbg(""); setDem(""); }
    } catch {
      setErro("Falha ao consultar a ANEEL (distribuidoras).");
    } finally {
      setCarregando(false);
    }
  };

  const trocarBase = (b: BaseId) => { setBase(b); void carregarBase(b); };

  const trocarDistribuidora = async (s: string) => {
    setSig(s); setErro(null); setCarregando(true);
    try { await carregarOpcoesDist(base, s); }
    catch { setErro("Falha ao consultar a ANEEL (subgrupos)."); setSubgrupos([]); setPorSub({}); setSbg(""); setDem(""); }
    finally { setCarregando(false); }
  };

  const trocarSubgrupo = (sb: string) => { setSbg(sb); setDem(porSub[sb]?.[0] ?? ""); };

  const toggleCampanha = () => {
    const abrir = !campAberta;
    setCampAberta(abrir);
    if (abrir && distribuidoras.length === 0) void carregarBase(base);
  };

  const aplicarCampanha = async () => {
    if (!sig || !sbg || !dem) return;
    setErro(null);
    setCarregando(true);
    try {
      const res = await carregarCampanha(base, sig, sbg, dem);
      setMatriz(res.payload.demanda_kw);
      setPonta(res.payload.energia_ponta_kwh);
      setFp(res.payload.energia_fp_kwh);
      setDemandaManual(res.payload.demanda_maxima_kw);
      setSerieUpload(res.serieDiaria);
      setFonteSerie(`Campanha ANEEL · ${res.meta.base} · ${res.meta.sig}/${res.meta.sbg} · ${res.meta.demandante}`);
      setAvisoUpload(
        `Campanha de Medição aplicada — ANEEL/CTR · ${res.meta.base} · ${res.meta.sig} / ${res.meta.sbg} · `
        + `${res.meta.demandante} · processo ${res.meta.ano} (${res.meta.processo}). `
        + "Curva-tipo (Dia Útil/Sábado/Domingo) expandida em ano representativo.",
      );
    } catch {
      setErro("Falha ao carregar a campanha de medição (ANEEL).");
    } finally {
      setCarregando(false);
    }
  };

  const limpar = () => {
    setMatriz(matrizZerada());
    setPonta(vetorZerado());
    setFp(vetorZerado());
    setDemandaManual(null);
    setSerieUpload(null);
    setFonteSerie(null);
    setAvisoUpload(null);
    // Fecha e reseta o quadro da Campanha de Medição.
    setCampAberta(false);
    setDistribuidoras([]);
    setSubgrupos([]);
    setPorSub({});
    setSig(""); setSbg(""); setDem("");
  };

  return (
    <div className="dashboard">
      <header className="topbar">
        <div>
          <strong>MOD 1 · Input de Carga</strong>
          <span className="muted"> · memória de massa (demanda 12×24 + energia)</span>
        </div>
        <div className="perfil">
          <label className="btn btn-google btn-sm" style={{ cursor: "pointer", margin: 0 }}>
            Memória de Massa
            <input
              type="file"
              accept=".csv,.tsv,.txt,.xlsx,.xls"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void importarArquivo(f);
                e.currentTarget.value = "";
              }}
            />
          </label>
          <button className="btn btn-ms btn-sm" disabled={carregando} onClick={toggleCampanha}>
            Campanha de Medição
          </button>
          <button className="btn-link" onClick={limpar}>Limpar</button>
          <Link className="btn-link" to="/">← Voltar</Link>
        </div>
      </header>

      <main>
        {erro && <p className="aviso">{erro}</p>}
        {avisoUpload && <div className="resultado ok">{avisoUpload}</div>}

        {/* Campanha de Medição — seletor da curva-tipo ANEEL/CTR */}
        {campAberta && (
          <section className="painel">
            <h3>Campanha de Medição — Curva-tipo ANEEL (CTR – Curva de Carga)</h3>
            <p className="muted" style={{ marginTop: -6 }}>
              Curvas de demanda de Rede/Consumidor Tipo das Revisões Tarifárias da ANEEL,
              consultadas via API (sem baixar CSV).
            </p>
            <div className="linha-campos">
              <label className="campo">
                <span>Base</span>
                <select value={base} onChange={(e) => trocarBase(e.target.value as BaseId)}>
                  {BASES_CTR.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
                </select>
              </label>
              <label className="campo">
                <span>Distribuidora</span>
                <select value={sig} onChange={(e) => void trocarDistribuidora(e.target.value)} disabled={distribuidoras.length === 0}>
                  {distribuidoras.length === 0
                    ? <option value="">—</option>
                    : distribuidoras.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
              <label className="campo">
                <span>Subgrupo</span>
                <select value={sbg} onChange={(e) => trocarSubgrupo(e.target.value)} disabled={subgrupos.length === 0}>
                  {subgrupos.length === 0
                    ? <option value="">—</option>
                    : subgrupos.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <label className="campo">
                <span>{base === "rede" ? "Rede tipo" : "Consumidor tipo"}</span>
                <select value={dem} onChange={(e) => setDem(e.target.value)} disabled={demandantes.length === 0}>
                  {demandantes.length === 0
                    ? <option value="">—</option>
                    : demandantes.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
            </div>
            <button className="btn btn-google btn-sm" disabled={carregando || !dem} onClick={() => void aplicarCampanha()}>
              {carregando ? "Consultando ANEEL…" : "Carregar curva"}
            </button>
          </section>
        )}

        {/* KPIs */}
        <div className="grid-kpis">
          <Kpi titulo="Demanda máxima" valor={`${fmt(local.demandaMaxima, 2)} kW`} />
          <Kpi titulo="Energia ponta (ano)" valor={`${fmt(local.pontaTotal)} kWh`} />
          <Kpi titulo="Energia fora-ponta (ano)" valor={`${fmt(local.fpTotal)} kWh`} />
          <Kpi titulo="Energia total (ano)" valor={`${fmt(local.pontaTotal + local.fpTotal)} kWh`} />
        </div>

        {/* Energia mensal — gráfico empilhado (Ponta + Fora-ponta) */}
        <EnergiaMensalChart ponta={ponta} fp={fp} />

        {/* Análise diária ao longo do ano (sem recurso de API — client-side) */}
        <DemandaDiariaChart serie={serieGrafico} fonte={fonteGrafico} />
      </main>
    </div>
  );
}

function Kpi({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div className="kpi">
      <div className="kpi-titulo">{titulo}</div>
      <div className="kpi-valor">{valor}</div>
    </div>
  );
}

