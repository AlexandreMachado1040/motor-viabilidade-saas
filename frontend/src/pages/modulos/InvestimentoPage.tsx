import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { mensagemDeErro } from "../../api/erros";
import { getExemploModulo, validarModulo } from "../../api/modulos";
import { DEMO_MODE } from "../../config";
import { useEstudo } from "../../estudo/useEstudo";
import type { PayloadModulo } from "../../types";
import { lerValores, valoresDoPayload, type ConfigInvestimento } from "./investimentos";

export function InvestimentoPage({ cfg }: { cfg: ConfigInvestimento }) {
  const { investimentos, definirInvestimento, limparInvestimento } = useEstudo();
  const salvo = investimentos[cfg.modulo];

  const [referencia, setReferencia] = useState<PayloadModulo | null>(null);
  const [tela, setTela] = useState<Record<string, string> | null>(null);
  const [erroCarga, setErroCarga] = useState<string | null>(null);
  const [erros, setErros] = useState<string[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    if (DEMO_MODE) return;
    let ativo = true;
    getExemploModulo(cfg.modulo)
      .then((ref) => {
        if (!ativo) return;
        setReferencia(ref);
        // O que já foi salvo no estudo tem prioridade sobre a referência.
        setTela(valoresDoPayload(cfg, salvo ?? ref));
      })
      .catch((e: unknown) => {
        if (ativo) setErroCarga(mensagemDeErro(e, "Não foi possível carregar os dados de referência."));
      });
    return () => {
      ativo = false;
    };
    // Preenchimento inicial só; depois a tela é a fonte da verdade.
  }, [cfg]);

  const alterar = (campo: string, valor: string) => {
    setTela((t) => (t ? { ...t, [campo]: valor } : t));
    setErros([]);
    setAviso(null);
  };

  const salvar = async () => {
    if (!tela || !referencia) return;
    const { valores, erros: errosTela } = lerValores(cfg, tela);
    setAviso(null);
    setErros(errosTela);
    if (!valores) return;
    const payload = cfg.montar(referencia, valores);
    setSalvando(true);
    try {
      const resumo = await validarModulo(cfg.modulo, payload);
      if (resumo.valido === false) {
        const lista = Array.isArray(resumo.erros) ? resumo.erros.map(String) : [];
        setErros(lista.length > 0 ? lista : ["O servidor rejeitou os dados."]);
        return;
      }
      definirInvestimento(cfg.modulo, payload);
      setAviso("Salvo no estudo. O Resumo do Estudo passa a usar estes valores.");
    } catch (e) {
      setErros([mensagemDeErro(e, "Falha inesperada ao validar os dados.")]);
    } finally {
      setSalvando(false);
    }
  };

  const restaurar = () => {
    if (!referencia) return;
    limparInvestimento(cfg.modulo);
    setTela(valoresDoPayload(cfg, referencia));
    setErros([]);
    setAviso("Voltou aos dados de referência.");
  };

  return (
    <div className="dashboard">
      <header className="topbar">
        <div>
          <strong>{cfg.titulo}</strong>
          <span className="muted"> · {cfg.subtitulo}</span>
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
              Estes dados alimentam o estudo calculado no servidor, que não está ativo nesta versão de demonstração.
            </p>
          </section>
        ) : erroCarga ? (
          <section className="painel">
            <div className="status-estudo falha">
              <strong>Tela indisponível</strong>
              <span>{erroCarga}</span>
            </div>
          </section>
        ) : !tela ? (
          <section className="painel">
            <p className="muted" style={{ margin: 0 }}>Carregando dados de referência…</p>
          </section>
        ) : (
          <section className="painel">
            <div className="acoes" style={{ marginTop: 0 }}>
              <span>
                Em uso no estudo: <strong>{salvo ? "valores personalizados" : "dados de referência"}</strong>
              </span>
              <Link className="btn-link" to="/modulos/summary">abrir o resumo</Link>
            </div>
            <p className="muted" style={{ fontSize: 12 }}>{cfg.nota}</p>

            <div className="linha-campos">
              {cfg.campos.map((c) => (
                <label key={c.campo} className="campo campo-tarifa" htmlFor={`${cfg.modulo}-${c.campo}`}>
                  {c.rotulo} ({c.unidade})
                  <input
                    id={`${cfg.modulo}-${c.campo}`}
                    inputMode="decimal"
                    value={tela[c.campo] ?? ""}
                    onChange={(e) => alterar(c.campo, e.target.value)}
                  />
                </label>
              ))}
            </div>

            <div className="acoes">
              <button type="button" className="btn btn-ms" onClick={() => void salvar()} disabled={salvando}>
                {salvando ? "Validando…" : "Salvar no estudo"}
              </button>
              {salvo && (
                <button type="button" className="btn-link" onClick={restaurar}>
                  Voltar aos dados de referência
                </button>
              )}
              {aviso && <span>{aviso}</span>}
            </div>
            {erros.length > 0 && (
              <div className="resultado falha">
                <strong>Corrija antes de salvar:</strong>
                <ul>{erros.map((e) => <li key={e}>{e}</li>)}</ul>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
