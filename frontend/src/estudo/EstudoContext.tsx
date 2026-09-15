import { createContext, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useAuth } from "../auth/useAuth";
import type { ModuloInvestimento } from "../api/modulos";
import type {
  InputLoadPayload, ModalidadeTarifaria, PayloadModulo, PicosMensais, SimuladorTarifasPayload,
} from "../types";

// Dados de entrada do estudo compartilhados entre as páginas de módulo.
// O load (MOD 1) é carregado numa tela e consumido pelo simulador de tarifas
// (MOD 2) e pelo resumo (MOD 10); a modalidade escolhida no simulador também
// segue para o resumo. sessionStorage para sobreviver a um recarregamento da
// página sem vazar entre abas; as chaves levam o id do usuário e o logout
// apaga as dele, para que outra conta na mesma aba não herde carga, tarifas
// ou CAPEX de quem saiu.
const CHAVE_LOAD = "motor-viabilidade:estudo:load";
const CHAVE_TARIFAS = "motor-viabilidade:estudo:tarifas";
const CHAVE_INVESTIMENTOS = "motor-viabilidade:estudo:investimentos";

// Solar, BESS de ponta e parâmetros financeiros editados nas telas próprias;
// módulo ausente = o resumo usa o dado de referência da planilha.
export type InvestimentosDoEstudo = Partial<Record<ModuloInvestimento, PayloadModulo>>;

export interface LoadDoEstudo {
  payload: InputLoadPayload;
  fonte: string;
  picos?: PicosMensais;
}

export interface TarifasDoEstudo {
  payload: SimuladorTarifasPayload;
  modalidade: ModalidadeTarifaria;
  nome: string;         // nome exibido ("Verde")
  custoAnual: number;   // fatura anual simulada da modalidade
  fonte: string;        // de onde vieram as medições
}

interface EstudoState {
  load: LoadDoEstudo | null;
  definirLoad: (payload: InputLoadPayload, fonte: string, picos?: PicosMensais) => void;
  limparLoad: () => void;
  tarifas: TarifasDoEstudo | null;
  definirTarifas: (tarifas: TarifasDoEstudo) => void;
  limparTarifas: () => void;
  investimentos: InvestimentosDoEstudo;
  definirInvestimento: (modulo: ModuloInvestimento, payload: PayloadModulo) => void;
  limparInvestimento: (modulo: ModuloInvestimento) => void;
}

export const EstudoContext = createContext<EstudoState | null>(null);

const CHAVES = [CHAVE_LOAD, CHAVE_TARIFAS, CHAVE_INVESTIMENTOS];
const chaveDe = (base: string, dono: number) => `${base}:${dono}`;

interface Estado {
  dono: number | null;
  load: LoadDoEstudo | null;
  tarifas: TarifasDoEstudo | null;
  investimentos: InvestimentosDoEstudo;
}

function lerTudo(dono: number | null): Estado {
  if (dono === null) return { dono, load: null, tarifas: null, investimentos: {} };
  return {
    dono,
    load: lerSalvo(chaveDe(CHAVE_LOAD, dono)),
    tarifas: lerSalvo(chaveDe(CHAVE_TARIFAS, dono)),
    investimentos: lerSalvo<InvestimentosDoEstudo>(chaveDe(CHAVE_INVESTIMENTOS, dono)) ?? {},
  };
}

const semInvestimentos = (v: InvestimentosDoEstudo) => Object.keys(v).length === 0;

function apagarTudo(dono: number | null): void {
  for (const base of CHAVES) salvar(dono === null ? base : chaveDe(base, dono), null);
}

function lerSalvo<T>(chave: string): T | null {
  try {
    const bruto = sessionStorage.getItem(chave);
    return bruto ? (JSON.parse(bruto) as T) : null;
  } catch {
    return null;
  }
}

function salvar(chave: string, valor: unknown): void {
  try {
    if (valor) sessionStorage.setItem(chave, JSON.stringify(valor));
    else sessionStorage.removeItem(chave);
  } catch {
    // armazenamento indisponível (modo privado, cota): segue só em memória
  }
}

export function EstudoProvider({ children }: { children: ReactNode }) {
  const { usuario } = useAuth();
  const dono = usuario?.id ?? null;
  const [estado, setEstado] = useState<Estado>(() => lerTudo(dono));

  // Troca de usuário (login, logout, outra conta): recarrega o estado do novo
  // dono no mesmo render, sem mostrar os dados do anterior nem por um quadro.
  if (estado.dono !== dono) setEstado(lerTudo(dono));

  const donoAnterior = useRef(dono);
  useEffect(() => {
    apagarTudo(null); // chaves sem usuário de versões anteriores
  }, []);
  useEffect(() => {
    if (donoAnterior.current !== null && donoAnterior.current !== dono) apagarTudo(donoAnterior.current);
    donoAnterior.current = dono;
  }, [dono]);

  // Atualiza uma parte do estado e persiste na chave do dono atual.
  const atualizar = useCallback(<K extends "load" | "tarifas" | "investimentos">(
    parte: K, base: string, calcular: (atual: Estado[K]) => Estado[K], vazio: (v: Estado[K]) => boolean,
  ) => {
    setEstado((e) => {
      const valor = calcular(e[parte]);
      if (e.dono !== null) salvar(chaveDe(base, e.dono), vazio(valor) ? null : valor);
      return { ...e, [parte]: valor };
    });
  }, []);

  const definirLoad = useCallback((payload: InputLoadPayload, fonte: string, picos?: PicosMensais) => {
    const valor: LoadDoEstudo = picos ? { payload, fonte, picos } : { payload, fonte };
    atualizar("load", CHAVE_LOAD, () => valor, (v) => v === null);
  }, [atualizar]);

  const limparLoad = useCallback(() => {
    atualizar("load", CHAVE_LOAD, () => null, () => true);
  }, [atualizar]);

  const definirTarifas = useCallback((valor: TarifasDoEstudo) => {
    atualizar("tarifas", CHAVE_TARIFAS, () => valor, (v) => v === null);
  }, [atualizar]);

  const limparTarifas = useCallback(() => {
    atualizar("tarifas", CHAVE_TARIFAS, () => null, () => true);
  }, [atualizar]);

  const definirInvestimento = useCallback((modulo: ModuloInvestimento, payload: PayloadModulo) => {
    atualizar("investimentos", CHAVE_INVESTIMENTOS, (atual) => ({ ...atual, [modulo]: payload }), semInvestimentos);
  }, [atualizar]);

  const limparInvestimento = useCallback((modulo: ModuloInvestimento) => {
    atualizar("investimentos", CHAVE_INVESTIMENTOS, (atual) => {
      const novo = { ...atual };
      delete novo[modulo];
      return novo;
    }, semInvestimentos);
  }, [atualizar]);

  const { load, tarifas, investimentos } = estado;
  const value = useMemo(
    () => ({
      load, definirLoad, limparLoad, tarifas, definirTarifas, limparTarifas,
      investimentos, definirInvestimento, limparInvestimento,
    }),
    [load, definirLoad, limparLoad, tarifas, definirTarifas, limparTarifas,
      investimentos, definirInvestimento, limparInvestimento],
  );
  return <EstudoContext.Provider value={value}>{children}</EstudoContext.Provider>;
}
