import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { mensagemDeErro } from "../../api/erros";
import { calcularEstudo, getExemploLoad, getExemploModulo } from "../../api/modulos";
import type { ModuloComExemplo } from "../../api/modulos";
import { useAuth } from "../../auth/useAuth";
import { DEMO_MODE } from "../../config";
import { useEstudo } from "../../estudo/useEstudo";
import type { InputLoadPayload, PayloadModulo, SummaryPayload, SummaryResumo } from "../../types";
import { fmt } from "./loadUtils";

type Investimento = "solar" | "bess_ponta";

interface Referencias {
  load?: InputLoadPayload;
  grid?: PayloadModulo;
  cf?: PayloadModulo;
  solar?: PayloadModulo;
  bess_ponta?: PayloadModulo;
}

// Módulos de investimento que o motor aceita, mas que ainda não têm tela nem
// dado de exemplo — listados só para deixar claro o que o estudo ignora.
const SEM_ENTRADA = [
  { id: "gen_ponta", rotulo: "Gerador diesel de ponta" },
  { id: "gen_form", rotulo: "Gerador formador de rede" },
  { id: "bess_form", rotulo: "BESS formador de rede" },
  { id: "new_grid", rotulo: "Nova rede elétrica" },
];

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const num = (o: PayloadModulo | undefined, campo: string): number | null => {
  const v = o?.[campo];
  return typeof v === "number" ? v : null;
};

const texto = (o: PayloadModulo | undefined, campo: string): string | null => {
  const v = o?.[campo];
  return typeof v === "string" ? v : null;
};


export function SummaryPage() {
  const { temModulo } = useAuth();
  const { load: loadUsuario } = useEstudo();

  const [refs, setRefs] = useState<Referencias>({});
  const [carregandoRefs, setCarregandoRefs] = useState(!DEMO_MODE);
  const [incluir, setIncluir] = useState<Record<Investimento, boolean>>({ solar: true, bess_ponta: true });
  const [calculando, setCalculando] = useState(false);
  const [resultado, setResultado] = useState<SummaryResumo | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (DEMO_MODE) return;
    let ativo = true;

    const buscar = async () => {
      const modulos: ModuloComExemplo[] = (["grid", "cf", "solar", "bess_ponta"] as const)
        .filter((m) => temModulo(m));
      const [loadRef, ...demais] = await Promise.allSettled([
        temModulo("load") ? getExemploLoad() : Promise.reject(new Error("sem licença")),
        ...modulos.map((m) => getExemploModulo(m)),
      ]);
      if (!ativo) return;

      const novas: Referencias = {};
      if (loadRef.status === "fulfilled") novas.load = loadRef.value;
      demais.forEach((r, i) => {
        if (r.status === "fulfilled") novas[modulos[i]] = r.value;
      });
      setRefs(novas);
      setCarregandoRefs(false);
    };

    void buscar();
    return () => {
      ativo = false;
    };
  }, [temModulo]);

  const loadEfetivo = loadUsuario?.payload ?? refs.load;
  const investimentosAtivos = (["solar", "bess_ponta"] as Investimento[])
    .filter((m) => incluir[m] && refs[m] !== undefined);
  const misturaCargaPropria = loadUsuario !== null && investimentosAtivos.length > 0;

  const faltando = useMemo(() => {
    const itens: string[] = [];
    if (!loadEfetivo) itens.push("carga (carregue a memória de massa no MOD 1)");
    if (!refs.grid) itens.push("tarifas da concessionária (módulo grid)");
    return itens;
  }, [loadEfetivo, refs.grid]);

  const alternar = (m: Investimento) => {
    setIncluir((atual) => ({ ...atual, [m]: !atual[m] }));
    setResultado(null);
  };

  const calcular = async () => {
    if (!loadEfetivo || !refs.grid) return;
    const payload: SummaryPayload = {
      load: loadEfetivo,
      grid: refs.grid,
      solar: incluir.solar && refs.solar ? refs.solar : null,
      bess_ponta: incluir.bess_ponta && refs.bess_ponta ? refs.bess_ponta : null,
    };
    if (refs.cf) payload.params_cf = refs.cf;

    setErro(null);
    setResultado(null);
    setCalculando(true);
    try {
      setResultado(await calcularEstudo(payload));
    } catch (e) {
      setErro(mensagemDeErro(e, "Falha inesperada ao calcular o estudo."));
    } finally {
      setCalculando(false);
    }
  };

  return (
    <div className="dashboard">
      <header className="topbar">
        <div>
          <strong>MOD 10 · Resumo do Estudo</strong>
          <span className="muted"> · viabilidade econômica do projeto completo</span>
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
              O estudo completo roda no motor de cálculo do servidor, que não está ativo nesta versão de
              demonstração. Use o ambiente com login para calcular VPL, TIR e payback.
            </p>
          </section>
        ) : (
          <>
            <section className="painel">
              <h3>Entradas do estudo</h3>
              {carregandoRefs ? (
                <p className="muted" style={{ margin: 0 }}>Carregando dados de referência…</p>
              ) : (
                <div className="entradas">
                  <Entrada
                    rotulo="Carga"
                    valor={
                      loadUsuario
                        ? loadUsuario.fonte
                        : refs.load
                          ? "Cenário de referência (planilha original)"
                          : "Indisponível"
                    }
                    detalhe={
                      <Link className="btn-link" to="/modulos/load">
                        {loadUsuario ? "Trocar no MOD 1" : "Carregar memória de massa"}
                      </Link>
                    }
                  />
                  <Entrada
                    rotulo="Tarifas"
                    valor={
                      refs.grid
                        ? `${texto(refs.grid, "concessionaria")} · ${texto(refs.grid, "subgrupo")} · ${texto(refs.grid, "modalidade")}`
                        : "Indisponível — módulo grid não licenciado"
                    }
                    detalhe={<span className="muted">referência</span>}
                  />
                  <Entrada
                    rotulo="Parâmetros financeiros"
                    valor={
                      refs.cf
                        ? `Desconto ${fmt((num(refs.cf, "taxa_desconto") ?? 0) * 100, 2)}% a.a. · ${num(refs.cf, "anos_projeto")} anos`
                        : "Padrão do motor · desconto 8% a.a. · 25 anos"
                    }
                    detalhe={<span className="muted">{refs.cf ? "referência" : "padrão"}</span>}
                  />
                </div>
              )}
            </section>

            {!carregandoRefs && (
              <section className="painel">
                <h3>Investimentos considerados</h3>
                <div className="entradas">
                  <OpcaoInvestimento
                    id="inv-solar"
                    rotulo="Solar (GD / compensação)"
                    disponivel={refs.solar !== undefined}
                    marcado={incluir.solar}
                    onAlternar={() => alternar("solar")}
                    resumo={
                      refs.solar
                        ? `${fmt(num(refs.solar, "potencia_cc_kwp") ?? 0)} kWp · CAPEX ${brl(num(refs.solar, "capex_r") ?? 0)}`
                        : "Módulo solar não licenciado"
                    }
                  />
                  <OpcaoInvestimento
                    id="inv-bess"
                    rotulo="BESS de ponta"
                    disponivel={refs.bess_ponta !== undefined}
                    marcado={incluir.bess_ponta}
                    onAlternar={() => alternar("bess_ponta")}
                    resumo={
                      refs.bess_ponta
                        ? `${fmt(num(refs.bess_ponta, "energia_dod80_kwh") ?? 0, 1)} kWh úteis · CAPEX ${brl(num(refs.bess_ponta, "capex_r") ?? 0)}`
                        : "Módulo bess_ponta não licenciado"
                    }
                  />
                  {SEM_ENTRADA.map((m) => (
                    <div key={m.id} className="entrada off">
                      <span className="entrada-rotulo">{m.rotulo}</span>
                      <span className="muted">sem tela de entrada ainda — fora do estudo</span>
                    </div>
                  ))}
                </div>
                {misturaCargaPropria && (
                  <p className="aviso" style={{ marginBottom: 0 }}>
                    Solar e BESS de referência foram dimensionados para a planilha original, não para a sua
                    carga. Use o resultado para explorar cenários, não como proposta.
                  </p>
                )}
              </section>
            )}

            {!carregandoRefs && (
              <div className="acoes">
                <button
                  className="btn btn-ms"
                  disabled={calculando || faltando.length > 0}
                  onClick={() => void calcular()}
                >
                  {calculando ? "Calculando…" : "Calcular estudo"}
                </button>
                {faltando.length > 0 && (
                  <span className="aviso">Falta: {faltando.join("; ")}.</span>
                )}
              </div>
            )}

            {erro && <div className="resultado falha">{erro}</div>}

            {resultado && !resultado.valido && (
              <div className="resultado falha">
                <strong>O estudo não pôde ser calculado com estes dados.</strong>
                <ul>
                  {resultado.erros.map((e) => <li key={e}>{e}</li>)}
                </ul>
              </div>
            )}

            {resultado?.valido && <Resultado r={resultado} />}
          </>
        )}
      </main>
    </div>
  );
}

function Entrada({ rotulo, valor, detalhe }: { rotulo: string; valor: string; detalhe: ReactNode }) {
  return (
    <div className="entrada">
      <span className="entrada-rotulo">{rotulo}</span>
      <span>{valor}</span>
      <span className="entrada-detalhe">{detalhe}</span>
    </div>
  );
}

function OpcaoInvestimento(props: {
  id: string;
  rotulo: string;
  disponivel: boolean;
  marcado: boolean;
  onAlternar: () => void;
  resumo: string;
}) {
  return (
    <div className={`entrada ${props.disponivel ? "" : "off"}`}>
      <label className="entrada-rotulo check" htmlFor={props.id}>
        <input
          id={props.id}
          type="checkbox"
          checked={props.disponivel && props.marcado}
          disabled={!props.disponivel}
          onChange={props.onAlternar}
        />
        {props.rotulo}
      </label>
      <span className={props.disponivel ? "" : "muted"}>{props.resumo}</span>
    </div>
  );
}

function Resultado({ r }: { r: SummaryResumo }) {
  const { vpl, tir_pct, payback, roi, viavel } = r.indicadores;
  const considerados = Object.entries(r.modulos_ativos)
    .filter(([m, ativo]) => ativo && !["cf", "summary"].includes(m))
    .map(([m]) => m);

  return (
    <section className="painel">
      <div className={`status-estudo ${viavel ? "ok" : "falha"}`}>
        <strong>{viavel ? "Estudo viável" : "Estudo não viável"}</strong>
        <span>
          {tir_pct === null
            ? "O fluxo de caixa não recupera o investimento no horizonte do projeto (TIR indefinida)."
            : viavel
              ? "A TIR supera a taxa de desconto do projeto."
              : "A TIR não supera a taxa de desconto do projeto."}
        </span>
      </div>

      <div className="grid-kpis">
        <Kpi titulo="VPL" valor={vpl === null ? "—" : brl(vpl)} />
        <Kpi titulo="TIR" valor={tir_pct === null ? "Indefinida" : `${fmt(tir_pct, 2)}% a.a.`} />
        <Kpi
          titulo="Payback"
          valor={payback === null ? "Não recupera" : `${payback} ${payback === 1 ? "ano" : "anos"}`}
        />
        <Kpi titulo="Retorno (VPL ÷ CAPEX)" valor={roi === null ? "—" : `${fmt(roi * 100, 1)}%`} />
      </div>

      <div className="detalhes-estudo">
        <dl>
          <dt>Concessionária</dt>
          <dd>{[r.projeto.concessionaria, r.projeto.subgrupo].filter(Boolean).join(" · ") || "—"}</dd>
          <dt>Demanda máxima</dt>
          <dd>{r.projeto.demanda_maxima_kw === null ? "—" : `${fmt(r.projeto.demanda_maxima_kw, 2)} kW`}</dd>
          <dt>Potência solar</dt>
          <dd>{r.projeto.potencia_solar_kwp === null ? "—" : `${fmt(r.projeto.potencia_solar_kwp)} kWp`}</dd>
          <dt>Energia do BESS</dt>
          <dd>{r.projeto.energia_bess_kwh === null ? "—" : `${fmt(r.projeto.energia_bess_kwh, 1)} kWh`}</dd>
        </dl>
        <dl>
          <dt>CAPEX total</dt>
          <dd>{r.custos.capex_total === null ? "—" : brl(r.custos.capex_total)}</dd>
          <dt>Custo anual da rede (sem projeto)</dt>
          <dd>{r.custos.opex_grid_anual === null ? "—" : brl(r.custos.opex_grid_anual)}</dd>
          <dt>Módulos no estudo</dt>
          <dd>{considerados.join(", ")}</dd>
        </dl>
      </div>
    </section>
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
