import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { mensagemDeErro } from "../../api/erros";
import { getExemploTarifas, simularTarifas } from "../../api/modulos";
import { DEMO_MODE } from "../../config";
import { useEstudo } from "../../estudo/useEstudo";
import type { LoadDoEstudo, TarifasDoEstudo } from "../../estudo/EstudoContext";
import type { ModalidadeTarifaria, SimuladorTarifasPayload, SimuladorTarifasResumo } from "../../types";
import { MESES, fmt } from "./loadUtils";

type Modalidade = ModalidadeTarifaria;
type SerieMensal = "demanda_ponta_kw" | "demanda_fp_kw" | "consumo_ponta_kwh" | "consumo_fp_kwh";

const SERIES: { campo: SerieMensal; rotulo: string }[] = [
  { campo: "demanda_ponta_kw", rotulo: "Demanda ponta (kW)" },
  { campo: "demanda_fp_kw", rotulo: "Demanda fora ponta (kW)" },
  { campo: "consumo_ponta_kwh", rotulo: "Consumo ponta (kWh)" },
  { campo: "consumo_fp_kwh", rotulo: "Consumo fora ponta (kWh)" },
];

// Campos de tarifa por modalidade. Os "úmido" são opcionais: vazio = mesma
// tarifa do período seco.
const CAMPOS: Record<Modalidade, { rotulo: string; campos: { id: string; rotulo: string; opcional?: boolean }[] }> = {
  convencional: {
    rotulo: "Convencional",
    campos: [
      { id: "demanda", rotulo: "Demanda (R$/kW)" },
      { id: "consumo", rotulo: "Consumo (R$/kWh)" },
    ],
  },
  azul: {
    rotulo: "Azul",
    campos: [
      { id: "demanda_ponta", rotulo: "Demanda ponta (R$/kW)" },
      { id: "demanda_fp", rotulo: "Demanda fora ponta (R$/kW)" },
      { id: "consumo_ponta", rotulo: "Consumo ponta (R$/kWh)" },
      { id: "consumo_fp", rotulo: "Consumo fora ponta (R$/kWh)" },
      { id: "consumo_ponta_umido", rotulo: "Consumo ponta úmido", opcional: true },
      { id: "consumo_fp_umido", rotulo: "Consumo fora ponta úmido", opcional: true },
    ],
  },
  verde: {
    rotulo: "Verde",
    campos: [
      { id: "demanda", rotulo: "Demanda (R$/kW)" },
      { id: "consumo_ponta", rotulo: "Consumo ponta (R$/kWh)" },
      { id: "consumo_fp", rotulo: "Consumo fora ponta (R$/kWh)" },
      { id: "consumo_ponta_umido", rotulo: "Consumo ponta úmido", opcional: true },
      { id: "consumo_fp_umido", rotulo: "Consumo fora ponta úmido", opcional: true },
    ],
  },
  baixa_tensao: {
    rotulo: "Baixa Tensão",
    campos: [{ id: "consumo", rotulo: "Consumo (R$/kWh)" }],
  },
};
const MODALIDADES = Object.keys(CAMPOS) as Modalidade[];

type Tarifas = Record<Modalidade, { incluir: boolean; valores: Record<string, string> }>;

interface Formulario {
  series: Record<SerieMensal, number[]>;
  contratada: number;
  contratadaPonta: number;
  contratadaFp: number;
  toleranciaPct: number;
  fator: number;
  tarifas: Tarifas;
  fonte: string;
  avisoFonte: string | null;
}

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const kw = (v: number | null) => (v == null ? "—" : `${fmt(v, 1)} kW`);

function tarifasDoExemplo(ex: SimuladorTarifasPayload): Tarifas {
  const tarifas = {} as Tarifas;
  for (const m of MODALIDADES) {
    const origem = ex[m] as Record<string, number | null | undefined> | null;
    const valores: Record<string, string> = {};
    for (const c of CAMPOS[m].campos) {
      const v = origem?.[c.id];
      valores[c.id] = v == null ? "" : String(v);
    }
    tarifas[m] = { incluir: origem !== null, valores };
  }
  return tarifas;
}

function formularioDoExemplo(ex: SimuladorTarifasPayload, load: LoadDoEstudo | null): Formulario {
  const form: Formulario = {
    series: {
      demanda_ponta_kw: ex.demanda_ponta_kw,
      demanda_fp_kw: ex.demanda_fp_kw,
      consumo_ponta_kwh: ex.consumo_ponta_kwh,
      consumo_fp_kwh: ex.consumo_fp_kwh,
    },
    contratada: ex.demanda_contratada_kw,
    contratadaPonta: ex.demanda_contratada_ponta_kw,
    contratadaFp: ex.demanda_contratada_fp_kw,
    toleranciaPct: ex.tolerancia_ultrapassagem * 100,
    fator: ex.fator_ultrapassagem,
    tarifas: tarifasDoExemplo(ex),
    fonte: "Exemplo da planilha Simulador de Tarifas",
    avisoFonte: null,
  };
  return load ? aplicarLoad(form, load) : form;
}

function aplicarLoad(form: Formulario, load: LoadDoEstudo): Formulario {
  const { picos } = load;
  if (!picos) {
    return {
      ...form,
      series: {
        ...form.series,
        consumo_ponta_kwh: load.payload.energia_ponta_kwh,
        consumo_fp_kwh: load.payload.energia_fp_kwh,
      },
      fonte: load.fonte,
      avisoFonte: "Esta carga é uma curva típica, sem a demanda máxima que a fatura cobra. O consumo veio da carga; "
        + "as demandas continuam as do exemplo. Digite as demandas medidas da fatura.",
    };
  }
  // Mês sem nenhuma leitura no arquivo mantém o valor que já estava na tabela,
  // em vez de virar zero e baratear a simulação.
  const semLeitura = MESES.filter((_, i) => picos.demanda_ponta_kw[i] == null && picos.demanda_fp_kw[i] == null);
  const escolher = (atual: number[], novo: (number | null)[], i: number, cobre: boolean) =>
    cobre ? (novo[i] ?? 0) : atual[i];
  const series: Record<SerieMensal, number[]> = {
    demanda_ponta_kw: MESES.map((m, i) =>
      escolher(form.series.demanda_ponta_kw, picos.demanda_ponta_kw, i, !semLeitura.includes(m))),
    demanda_fp_kw: MESES.map((m, i) =>
      escolher(form.series.demanda_fp_kw, picos.demanda_fp_kw, i, !semLeitura.includes(m))),
    consumo_ponta_kwh: MESES.map((m, i) =>
      semLeitura.includes(m) ? form.series.consumo_ponta_kwh[i] : load.payload.energia_ponta_kwh[i]),
    consumo_fp_kwh: MESES.map((m, i) =>
      semLeitura.includes(m) ? form.series.consumo_fp_kwh[i] : load.payload.energia_fp_kwh[i]),
  };
  return {
    ...form,
    series,
    fonte: load.fonte,
    avisoFonte: semLeitura.length > 0
      ? `O arquivo não tem leituras em ${semLeitura.join(", ")}. Esses meses mantiveram os valores anteriores `
        + "da tabela — confira com a fatura antes de simular."
      : null,
  };
}

/** Monta o payload; devolve a lista de campos inválidos em vez de enviar lixo. */
function montarPayload(form: Formulario): { payload?: SimuladorTarifasPayload; erros: string[] } {
  const erros: string[] = [];
  const payload: SimuladorTarifasPayload = {
    ...form.series,
    demanda_contratada_kw: form.contratada,
    demanda_contratada_ponta_kw: form.contratadaPonta,
    demanda_contratada_fp_kw: form.contratadaFp,
    tolerancia_ultrapassagem: form.toleranciaPct / 100,
    fator_ultrapassagem: form.fator,
    convencional: null,
    azul: null,
    verde: null,
    baixa_tensao: null,
  };
  for (const m of MODALIDADES) {
    const t = form.tarifas[m];
    if (!t.incluir) continue;
    const valores: Record<string, number | null> = {};
    for (const c of CAMPOS[m].campos) {
      const bruto = t.valores[c.id]?.trim().replace(",", ".") ?? "";
      if (bruto === "") {
        if (c.opcional) { valores[c.id] = null; continue; }
        erros.push(`${CAMPOS[m].rotulo}: informe ${c.rotulo.toLowerCase()}.`);
        continue;
      }
      const v = Number(bruto);
      if (!Number.isFinite(v) || v < 0) {
        erros.push(`${CAMPOS[m].rotulo}: ${c.rotulo.toLowerCase()} deve ser um número positivo.`);
        continue;
      }
      valores[c.id] = v;
    }
    (payload as unknown as Record<Modalidade, unknown>)[m] = valores;
  }
  if (!MODALIDADES.some((m) => form.tarifas[m].incluir)) {
    erros.push("Inclua pelo menos uma modalidade.");
  }
  return erros.length > 0 ? { erros } : { payload, erros };
}

export function GridPage() {
  const { load, tarifas: tarifasNoEstudo, definirTarifas } = useEstudo();
  const [exemplo, setExemplo] = useState<SimuladorTarifasPayload | null>(null);
  const [form, setForm] = useState<Formulario | null>(null);
  const [erroCarga, setErroCarga] = useState<string | null>(null);
  const [errosForm, setErrosForm] = useState<string[]>([]);
  const [simulando, setSimulando] = useState(false);
  const [resultado, setResultado] = useState<SimuladorTarifasResumo | null>(null);
  // Payload exatamente como foi simulado — é o que segue para o estudo.
  const [simulado, setSimulado] = useState<{ payload: SimuladorTarifasPayload; fonte: string } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (DEMO_MODE) return;
    let ativo = true;
    getExemploTarifas()
      .then((ex) => {
        if (!ativo) return;
        setExemplo(ex);
        setForm(formularioDoExemplo(ex, load));
      })
      .catch((e: unknown) => {
        if (ativo) setErroCarga(mensagemDeErro(e, "Não foi possível carregar o exemplo de tarifas."));
      });
    return () => {
      ativo = false;
    };
    // O load só entra no preenchimento inicial; trocar depois é pelos botões.
  }, []);

  const alterar = (muda: (f: Formulario) => Formulario) => {
    setForm((f) => (f ? muda(f) : f));
    setResultado(null);
    setErrosForm([]);
  };

  const alterarMes = (campo: SerieMensal, mes: number, valor: string) =>
    alterar((f) => {
      const serie = [...f.series[campo]];
      serie[mes] = Math.max(0, Number(valor) || 0);
      return { ...f, series: { ...f.series, [campo]: serie } };
    });

  const alterarTarifa = (m: Modalidade, campo: string, valor: string) =>
    alterar((f) => ({
      ...f,
      tarifas: { ...f.tarifas, [m]: { ...f.tarifas[m], valores: { ...f.tarifas[m].valores, [campo]: valor } } },
    }));

  const simular = async () => {
    if (!form) return;
    const { payload, erros } = montarPayload(form);
    setErro(null);
    setResultado(null);
    setErrosForm(erros);
    if (!payload) return;
    setSimulando(true);
    try {
      setResultado(await simularTarifas(payload));
      setSimulado({ payload, fonte: form.fonte });
    } catch (e) {
      setErro(mensagemDeErro(e, "Falha inesperada ao simular as tarifas."));
    } finally {
      setSimulando(false);
    }
  };

  return (
    <div className="dashboard">
      <header className="topbar">
        <div>
          <strong>MOD 2 · Simulador de Tarifas</strong>
          <span className="muted"> · qual modalidade sai mais barata para esta carga</span>
        </div>
        <div className="perfil">
          <Link className="btn-link" to="/">← Voltar</Link>
        </div>
      </header>

      <main>
        {DEMO_MODE ? (
          <section className="painel">
            <h3>Indisponível no modo demonstração</h3>
            <p className="muted" style={{ margin: 0 }}>
              A simulação roda no motor de cálculo do servidor, que não está ativo nesta versão de
              demonstração. Use o ambiente com login para comparar as modalidades.
            </p>
          </section>
        ) : erroCarga ? (
          <section className="painel">
            <div className="status-estudo falha">
              <strong>Simulador indisponível</strong>
              <span>{erroCarga}</span>
            </div>
          </section>
        ) : !form || !exemplo ? (
          <section className="painel">
            <p className="muted" style={{ margin: 0 }}>Carregando exemplo de tarifas…</p>
          </section>
        ) : (
          <>
            <section className="painel">
              <h3>Consumo e demanda medidos</h3>
              <div className="acoes" style={{ marginTop: 0 }}>
                <span>Fonte: <strong>{form.fonte}</strong></span>
                {load && form.fonte !== load.fonte && (
                  <button type="button" className="btn-link" onClick={() => alterar((f) => aplicarLoad(f, load))}>
                    Usar a carga do MOD 1
                  </button>
                )}
                {form.fonte !== "Exemplo da planilha Simulador de Tarifas" && (
                  <button type="button" className="btn-link" onClick={() => alterar((f) => {
                    // Só as medições voltam ao exemplo; tarifas e contratadas digitadas ficam.
                    const ex = formularioDoExemplo(exemplo, null);
                    return { ...f, series: ex.series, fonte: ex.fonte, avisoFonte: null };
                  })}>
                    Usar dados do exemplo
                  </button>
                )}
                {!load && (
                  <Link className="btn-link" to="/modulos/load">Carregar memória de massa</Link>
                )}
              </div>
              {form.avisoFonte && <p className="aviso">{form.avisoFonte}</p>}
              <div className="tabela-wrap">
                <table className="tabela-energia">
                  <thead>
                    <tr>
                      <th className="sticky-col" />
                      {MESES.map((m) => <th key={m}>{m}</th>)}
                      <th>Ano</th>
                    </tr>
                  </thead>
                  <tbody>
                    {SERIES.map(({ campo, rotulo }) => {
                      const serie = form.series[campo];
                      const consumo = campo.startsWith("consumo");
                      return (
                        <tr key={campo}>
                          <th className="sticky-col" style={{ textAlign: "left", whiteSpace: "nowrap" }}>{rotulo}</th>
                          {serie.map((v, i) => (
                            <td key={i}>
                              <input
                                className="cel-num"
                                type="number"
                                min={0}
                                step="any"
                                aria-label={`${rotulo} · ${MESES[i]}`}
                                value={v}
                                onChange={(e) => alterarMes(campo, i, e.target.value)}
                              />
                            </td>
                          ))}
                          <td className="ro">
                            {consumo
                              ? fmt(serie.reduce((a, b) => a + b, 0))
                              : `máx ${fmt(Math.max(...serie), 1)}`}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="painel">
              <h3>Demanda contratada</h3>
              <div className="linha-campos">
                <CampoNumero id="contratada" rotulo="Convencional e Verde (kW)" valor={form.contratada}
                  onChange={(v) => alterar((f) => ({ ...f, contratada: v }))} />
                <CampoNumero id="contratada-ponta" rotulo="Azul · ponta (kW)" valor={form.contratadaPonta}
                  onChange={(v) => alterar((f) => ({ ...f, contratadaPonta: v }))} />
                <CampoNumero id="contratada-fp" rotulo="Azul · fora ponta (kW)" valor={form.contratadaFp}
                  onChange={(v) => alterar((f) => ({ ...f, contratadaFp: v }))} />
                <CampoNumero id="tolerancia" rotulo="Tolerância de ultrapassagem (%)" valor={form.toleranciaPct}
                  onChange={(v) => alterar((f) => ({ ...f, toleranciaPct: v }))} />
                <CampoNumero id="fator" rotulo="Multiplicador da ultrapassagem" valor={form.fator}
                  onChange={(v) => alterar((f) => ({ ...f, fator: v }))} />
              </div>
            </section>

            <section className="painel">
              <h3>Tarifas por modalidade</h3>
              <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>
                Valores finais da fatura, com impostos se for o caso. Úmido (dez–abr) em branco usa a tarifa do
                período seco.
              </p>
              <div className="entradas">
                {MODALIDADES.map((m) => {
                  const t = form.tarifas[m];
                  return (
                    <div key={m} className={`tarifa-modalidade${t.incluir ? "" : " off"}`}>
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={t.incluir}
                          onChange={() => alterar((f) => ({
                            ...f, tarifas: { ...f.tarifas, [m]: { ...f.tarifas[m], incluir: !t.incluir } },
                          }))}
                        />
                        {CAMPOS[m].rotulo}
                      </label>
                      <div className="linha-campos">
                        {CAMPOS[m].campos.map((c) => (
                          <label key={c.id} className="campo campo-tarifa" htmlFor={`${m}-${c.id}`}>
                            {c.rotulo}
                            <input
                              id={`${m}-${c.id}`}
                              inputMode="decimal"
                              disabled={!t.incluir}
                              placeholder={c.opcional ? "= seco" : ""}
                              value={t.valores[c.id] ?? ""}
                              onChange={(e) => alterarTarifa(m, c.id, e.target.value)}
                            />
                          </label>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="acoes">
                <button type="button" className="btn btn-ms" onClick={() => void simular()} disabled={simulando}>
                  {simulando ? "Simulando…" : "Simular modalidades"}
                </button>
              </div>
              {errosForm.length > 0 && (
                <div className="resultado falha">
                  <strong>Corrija antes de simular:</strong>
                  <ul>{errosForm.map((e) => <li key={e}>{e}</li>)}</ul>
                </div>
              )}
              {erro && <div className="resultado falha">{erro}</div>}
            </section>

            {resultado && <Resultado r={resultado} />}
            {resultado?.valido && simulado && (
              <UsarNoEstudo
                r={resultado}
                emUso={tarifasNoEstudo}
                onUsar={(modalidade) => {
                  const m = resultado.modalidades.find((x) => x.modalidade === CAMPOS[modalidade].rotulo);
                  if (!m) return;
                  definirTarifas({
                    payload: simulado.payload, modalidade, nome: m.modalidade,
                    custoAnual: m.custo_anual, fonte: simulado.fonte,
                  });
                }}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

function UsarNoEstudo({ r, emUso, onUsar }: {
  r: SimuladorTarifasResumo;
  emUso: TarifasDoEstudo | null;
  onUsar: (m: Modalidade) => void;
}) {
  const disponiveis = MODALIDADES.filter((m) => r.modalidades.some((x) => x.modalidade === CAMPOS[m].rotulo));
  const recomendada = disponiveis.find((m) => CAMPOS[m].rotulo === r.recomendada) ?? disponiveis[0];
  const [escolha, setEscolha] = useState<Modalidade | undefined>(recomendada);
  if (!escolha) return null;
  return (
    <section className="painel">
      <h3>Usar no Resumo do Estudo</h3>
      <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>
        A fatura da modalidade escolhida vira o custo da rede do estudo, e as tarifas médias de consumo dela
        calculam a economia de solar e BESS.
      </p>
      <div className="acoes" style={{ marginTop: 0 }}>
        <label className="campo" htmlFor="modalidade-estudo">
          Modalidade
          <select id="modalidade-estudo" value={escolha} onChange={(e) => setEscolha(e.target.value as Modalidade)}>
            {disponiveis.map((m) => (
              <option key={m} value={m}>
                {CAMPOS[m].rotulo}{CAMPOS[m].rotulo === r.recomendada ? " (recomendada)" : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn btn-ms" onClick={() => onUsar(escolha)}>
          Usar no estudo
        </button>
        {emUso && (
          <span>
            Em uso no estudo: <strong>{emUso.nome}</strong> ·{" "}
            <Link className="btn-link" to="/modulos/summary">abrir o resumo</Link>
          </span>
        )}
      </div>
    </section>
  );
}

function CampoNumero({ id, rotulo, valor, onChange }: {
  id: string; rotulo: string; valor: number; onChange: (v: number) => void;
}) {
  return (
    <label className="campo campo-tarifa" htmlFor={id}>
      {rotulo}
      <input id={id} type="number" min={0} step="any" value={valor}
        onChange={(e) => onChange(Math.max(0, Number(e.target.value) || 0))} />
    </label>
  );
}

function Resultado({ r }: { r: SimuladorTarifasResumo }) {
  if (!r.valido) {
    return (
      <section className="painel">
        <div className="status-estudo falha">
          <strong>A simulação não pôde ser feita com estes dados.</strong>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {r.erros.map((e) => <li key={e}>{e}</li>)}
          </ul>
        </div>
      </section>
    );
  }
  const ordenadas = [...r.modalidades].sort((a, b) => a.custo_anual - b.custo_anual);
  const segunda = ordenadas[1];
  return (
    <section className="painel">
      <h3>Resultado</h3>
      {r.recomendada && (
        <div className="status-estudo ok">
          <strong>Modalidade recomendada: {r.recomendada}</strong>
          <span>
            {brl(ordenadas[0].custo_anual)} por ano
            {segunda && ` · ${brl(segunda.custo_anual - ordenadas[0].custo_anual)} a menos que ${segunda.modalidade}`}
          </span>
        </div>
      )}

      <div className="tabela-wrap">
        <table className="tabela-admin">
          <thead>
            <tr>
              <th>Modalidade</th>
              <th>Custo anual</th>
              <th>Diferença</th>
              <th>Ultrapassagem</th>
              <th>Componentes</th>
            </tr>
          </thead>
          <tbody>
            {ordenadas.map((m) => (
              <tr key={m.modalidade}>
                <td><strong>{m.modalidade}</strong></td>
                <td className="num">{brl(m.custo_anual)}</td>
                <td className="num">{m.modalidade === r.recomendada ? "—" : `+ ${brl(r.economia_vs_atual[m.modalidade] ?? 0)}`}</td>
                <td className="num">
                  {m.meses_com_ultrapassagem > 0
                    ? `${brl(m.ultrapassagem_anual)} · ${m.meses_com_ultrapassagem} ${m.meses_com_ultrapassagem === 1 ? "mês" : "meses"}`
                    : "nenhuma"}
                </td>
                <td className="componentes">
                  {Object.entries(m.componentes)
                    .filter(([, v]) => v !== 0)
                    .map(([k, v]) => `${k} ${brl(v)}`)
                    .join(" · ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {r.demandas_sugeridas.length > 0 && (
        <>
          <h3 style={{ marginTop: 18 }}>Demanda contratada que minimiza o custo</h3>
          <div className="tabela-wrap">
            <table className="tabela-admin">
              <thead>
                <tr>
                  <th>Modalidade</th>
                  <th>Contratar</th>
                  <th>Custo anual</th>
                  <th>Economia vs. contratada atual</th>
                </tr>
              </thead>
              <tbody>
                {r.demandas_sugeridas.map((s) => (
                  <tr key={s.modalidade}>
                    <td><strong>{s.modalidade}</strong></td>
                    <td>
                      {s.demanda_kw != null
                        ? kw(s.demanda_kw)
                        : `ponta ${kw(s.demanda_ponta_kw)} · fora ponta ${kw(s.demanda_fp_kw)}`}
                    </td>
                    <td className="num">{brl(s.custo_anual)}</td>
                    <td className="num">{s.economia_anual > 0.5 ? brl(s.economia_anual) : "já é a ideal"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
            Calculada sobre os 12 meses informados. Confira os limites de contratação da distribuidora antes de
            pedir a alteração.
          </p>
        </>
      )}
    </section>
  );
}
