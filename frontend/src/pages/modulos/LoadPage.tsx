import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { validarLoad } from "../../api/modulos";
import type { InputLoadPayload, LoadResumo } from "../../types";
import {
  fmt, matrizZerada, serieDiariaDeMatriz, vetorZerado,
} from "./loadUtils";
import { interpretar, lerPlanilha } from "./loadUpload";
import { DemandaDiariaChart } from "./DemandaDiariaChart";
import { EnergiaMensalChart } from "./EnergiaMensalChart";
import { carregarCampanha, DISTRIBUIDORAS, listarDemandantes, SUBGRUPOS } from "./campanhaAneel";
import type { DiaDemanda } from "../../types";

export function LoadPage() {
  const [matriz, setMatriz] = useState<number[][]>(matrizZerada);
  const [ponta, setPonta] = useState<number[]>(vetorZerado);
  const [fp, setFp] = useState<number[]>(vetorZerado);
  const [demandaManual, setDemandaManual] = useState<number | null>(null);
  const [resumo, setResumo] = useState<LoadResumo | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [avisoUpload, setAvisoUpload] = useState<string | null>(null);
  const [serieUpload, setSerieUpload] = useState<DiaDemanda[] | null>(null);
  const [fonteSerie, setFonteSerie] = useState<string | null>(null);

  // Campanha de Medição (curva-tipo ANEEL/CTR).
  const [campAberta, setCampAberta] = useState(false);
  const [sig, setSig] = useState("CEMIG");
  const [sbg, setSbg] = useState<string>("A4");
  const [demandantes, setDemandantes] = useState<string[]>([]);
  const [dem, setDem] = useState<string>("");

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
      setResumo(null);
      setAvisoUpload(r.aviso);
    } catch {
      setErro("Falha ao ler o arquivo. Verifique o formato/codificação.");
    } finally {
      setCarregando(false);
    }
  };

  // ── Campanha de Medição (curva-tipo ANEEL/CTR) ────────────────────────────
  const buscarDemandantes = async (s: string, g: string) => {
    setErro(null);
    setCarregando(true);
    try {
      const lista = await listarDemandantes(s, g);
      setDemandantes(lista);
      setDem(lista[0] ?? "");
      if (lista.length === 0) setErro(`Sem curva-tipo para ${s} / ${g}. Tente outro subgrupo.`);
    } catch {
      setErro("Falha ao consultar a ANEEL (demandantes).");
      setDemandantes([]); setDem("");
    } finally {
      setCarregando(false);
    }
  };

  const trocarSelecao = (s: string, g: string) => {
    setSig(s); setSbg(g);
    void buscarDemandantes(s, g);
  };

  const toggleCampanha = () => {
    const abrir = !campAberta;
    setCampAberta(abrir);
    if (abrir && demandantes.length === 0) void buscarDemandantes(sig, sbg);
  };

  const aplicarCampanha = async () => {
    if (!dem) return;
    setErro(null);
    setCarregando(true);
    try {
      const res = await carregarCampanha(sig, sbg, dem);
      setMatriz(res.payload.demanda_kw);
      setPonta(res.payload.energia_ponta_kwh);
      setFp(res.payload.energia_fp_kwh);
      setDemandaManual(res.payload.demanda_maxima_kw);
      setSerieUpload(res.serieDiaria);
      setFonteSerie(`Campanha ANEEL · ${res.meta.sig}/${res.meta.sbg} · ${res.meta.demandante}`);
      setResumo(null);
      setAvisoUpload(
        `Campanha de Medição aplicada — ANEEL/CTR · ${res.meta.sig} / ${res.meta.sbg} · `
        + `${res.meta.demandante} · processo ${res.meta.ano} (${res.meta.processo}). `
        + "Curva-tipo (Dia Útil/Sábado/Domingo) expandida em ano representativo.",
      );
    } catch {
      setErro("Falha ao carregar a campanha de medição (ANEEL).");
    } finally {
      setCarregando(false);
    }
  };

  const validar = async () => {
    setErro(null);
    setCarregando(true);
    const payload: InputLoadPayload = {
      demanda_maxima_kw: demandaManual,
      demanda_kw: matriz,
      energia_ponta_kwh: ponta,
      energia_fp_kwh: fp,
    };
    try {
      setResumo(await validarLoad(payload));
    } catch {
      setErro("Falha ao validar no servidor.");
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
    setResumo(null);
    setAvisoUpload(null);
    // Fecha e reseta o quadro da Campanha de Medição.
    setCampAberta(false);
    setDemandantes([]);
    setDem("");
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
            Importar arquivo
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
                <span>Distribuidora</span>
                <select value={sig} onChange={(e) => trocarSelecao(e.target.value, sbg)}>
                  {DISTRIBUIDORAS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
              <label className="campo">
                <span>Subgrupo (tensão)</span>
                <select value={sbg} onChange={(e) => trocarSelecao(sig, e.target.value)}>
                  {SUBGRUPOS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <label className="campo">
                <span>Rede/Consumidor tipo</span>
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

        {/* Validação no servidor */}
        <section className="painel">
          <button className="btn btn-google" disabled={carregando} onClick={() => void validar()}>
            {carregando ? "Processando…" : "Validar no servidor"}
          </button>

          {resumo && (
            <div className={`resultado ${resumo.valido ? "ok" : "falha"}`}>
              {resumo.valido ? (
                <>
                  <strong>✓ Memória de massa válida</strong>
                  <div className="grid-kpis">
                    <Kpi titulo="Demanda máx. (motor)" valor={`${fmt(resumo.demanda_maxima_kw, 2)} kW`} />
                    <Kpi titulo="Ponta total" valor={`${fmt(resumo.energia_ponta_total)} kWh`} />
                    <Kpi titulo="Fora-ponta total" valor={`${fmt(resumo.energia_fp_total)} kWh`} />
                    <Kpi titulo="Total" valor={`${fmt(resumo.energia_total)} kWh`} />
                  </div>
                </>
              ) : (
                <>
                  <strong>✗ Há inconsistências:</strong>
                  <ul>{resumo.erros.map((e) => <li key={e}>{e}</li>)}</ul>
                </>
              )}
            </div>
          )}
        </section>
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

