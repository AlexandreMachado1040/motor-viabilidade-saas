import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getExemploLoad, validarLoad } from "../../api/modulos";
import type { InputLoadPayload, LoadResumo } from "../../types";
import {
  fmt, HORAS, matrizZerada, MESES, parseMatrizColada, vetorZerado,
} from "./loadUtils";
import { interpretar, lerPlanilha } from "./loadUpload";

export function LoadPage() {
  const [matriz, setMatriz] = useState<number[][]>(matrizZerada);
  const [ponta, setPonta] = useState<number[]>(vetorZerado);
  const [fp, setFp] = useState<number[]>(vetorZerado);
  const [demandaManual, setDemandaManual] = useState<number | null>(null);
  const [colagem, setColagem] = useState("");
  const [resumo, setResumo] = useState<LoadResumo | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [avisoUpload, setAvisoUpload] = useState<string | null>(null);

  // ── Derivados locais (preview imediato) ──────────────────────────────────
  const local = useMemo(() => {
    const picoMensal = matriz.map((linha) => Math.max(0, ...linha));
    const picoGeral = Math.max(0, ...picoMensal);
    return {
      picoMensal,
      demandaMaxima: demandaManual ?? picoGeral,
      pontaTotal: ponta.reduce((a, b) => a + b, 0),
      fpTotal: fp.reduce((a, b) => a + b, 0),
    };
  }, [matriz, ponta, fp, demandaManual]);

  // ── Edição ───────────────────────────────────────────────────────────────
  const setCelula = (i: number, j: number, v: number) =>
    setMatriz((m) => m.map((lin, li) => (li === i ? lin.map((c, cj) => (cj === j ? v : c)) : lin)));

  const setVetor = (
    setter: React.Dispatch<React.SetStateAction<number[]>>, i: number, v: number,
  ) => setter((arr) => arr.map((c, ci) => (ci === i ? v : c)));

  const aplicarColagem = () => {
    if (!colagem.trim()) return;
    setMatriz(parseMatrizColada(colagem));
    setColagem("");
  };

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
      setResumo(null);
      setAvisoUpload(r.aviso);
    } catch {
      setErro("Falha ao ler o arquivo. Verifique o formato/codificação.");
    } finally {
      setCarregando(false);
    }
  };

  const carregarExemplo = async () => {
    setErro(null);
    setCarregando(true);
    try {
      const ex = await getExemploLoad();
      setMatriz(ex.demanda_kw);
      setPonta(ex.energia_ponta_kwh);
      setFp(ex.energia_fp_kwh);
      setDemandaManual(ex.demanda_maxima_kw);
      setResumo(null);
    } catch {
      setErro("Falha ao carregar o exemplo (verifique a licença/servidor).");
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
    setResumo(null);
    setAvisoUpload(null);
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
          <button className="btn btn-ms btn-sm" disabled={carregando} onClick={() => void carregarExemplo()}>
            Carregar exemplo
          </button>
          <button className="btn-link" onClick={limpar}>Limpar</button>
          <Link className="btn-link" to="/">← Voltar</Link>
        </div>
      </header>

      <main>
        {erro && <p className="aviso">{erro}</p>}
        {avisoUpload && <div className="resultado ok">{avisoUpload}</div>}

        {/* KPIs */}
        <div className="grid-kpis">
          <Kpi titulo="Demanda máxima" valor={`${fmt(local.demandaMaxima, 2)} kW`} />
          <Kpi titulo="Energia ponta (ano)" valor={`${fmt(local.pontaTotal)} kWh`} />
          <Kpi titulo="Energia fora-ponta (ano)" valor={`${fmt(local.fpTotal)} kWh`} />
          <Kpi titulo="Energia total (ano)" valor={`${fmt(local.pontaTotal + local.fpTotal)} kWh`} />
        </div>

        {/* Demanda manual + colagem */}
        <section className="painel">
          <div className="linha-campos">
            <label className="campo">
              <span>Demanda contratada/máx. (kW) — vazio = pico da matriz</span>
              <input
                type="number" step="0.01"
                value={demandaManual ?? ""}
                placeholder={fmt(local.demandaMaxima, 2)}
                onChange={(e) => setDemandaManual(e.target.value === "" ? null : Number(e.target.value))}
              />
            </label>
          </div>
          <div className="colagem">
            <textarea
              value={colagem}
              onChange={(e) => setColagem(e.target.value)}
              placeholder="Cole aqui 12 linhas × 24 colunas da planilha (tab/; entre colunas, decimal pt-BR)…"
              rows={3}
            />
            <button className="btn btn-ms btn-sm" onClick={aplicarColagem}>Aplicar colagem</button>
          </div>
        </section>

        {/* Energia mensal */}
        <section className="painel">
          <h3>Energia mensal (kWh)</h3>
          <div className="tabela-wrap">
            <table className="tabela-energia">
              <thead>
                <tr><th>Mês</th><th>Ponta</th><th>Fora-ponta</th><th>Equivalente</th></tr>
              </thead>
              <tbody>
                {MESES.map((mes, i) => (
                  <tr key={mes}>
                    <td>{mes}</td>
                    <td><CelNum value={ponta[i]} onChange={(v) => setVetor(setPonta, i, v)} /></td>
                    <td><CelNum value={fp[i]} onChange={(v) => setVetor(setFp, i, v)} /></td>
                    <td className="ro">{fmt(ponta[i] + fp[i])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Matriz 12×24 */}
        <section className="painel">
          <h3>Memória de massa — demanda (kW) · 12 meses × 24 horas</h3>
          <div className="tabela-wrap">
            <table className="tabela-massa">
              <thead>
                <tr>
                  <th className="sticky-col">Mês\\Hora</th>
                  {HORAS.map((h) => <th key={h}>{h}h</th>)}
                  <th>Pico</th>
                </tr>
              </thead>
              <tbody>
                {MESES.map((mes, i) => (
                  <tr key={mes}>
                    <td className="sticky-col">{mes}</td>
                    {HORAS.map((h) => (
                      <td key={h}>
                        <CelNum compact value={matriz[i][h]} onChange={(v) => setCelula(i, h, v)} />
                      </td>
                    ))}
                    <td className="ro">{fmt(local.picoMensal[i])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

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

function CelNum({
  value, onChange, compact,
}: { value: number; onChange: (v: number) => void; compact?: boolean }) {
  return (
    <input
      type="number"
      className={compact ? "cel-num compact" : "cel-num"}
      value={value}
      onChange={(e) => onChange(Number(e.target.value) || 0)}
    />
  );
}
