import { createContext, useCallback, useMemo, useState, type ReactNode } from "react";
import type { InputLoadPayload, ModalidadeTarifaria, PicosMensais, SimuladorTarifasPayload } from "../types";

// Dados de entrada do estudo compartilhados entre as páginas de módulo.
// O load (MOD 1) é carregado numa tela e consumido pelo simulador de tarifas
// (MOD 2) e pelo resumo (MOD 10); a modalidade escolhida no simulador também
// segue para o resumo. sessionStorage para sobreviver a um recarregamento da
// página sem vazar entre abas/sessões.
const CHAVE_LOAD = "motor-viabilidade:estudo:load";
const CHAVE_TARIFAS = "motor-viabilidade:estudo:tarifas";

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
}

export const EstudoContext = createContext<EstudoState | null>(null);

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
  const [load, setLoad] = useState<LoadDoEstudo | null>(() => lerSalvo(CHAVE_LOAD));
  const [tarifas, setTarifas] = useState<TarifasDoEstudo | null>(() => lerSalvo(CHAVE_TARIFAS));

  const definirLoad = useCallback((payload: InputLoadPayload, fonte: string, picos?: PicosMensais) => {
    const valor: LoadDoEstudo = picos ? { payload, fonte, picos } : { payload, fonte };
    setLoad(valor);
    salvar(CHAVE_LOAD, valor);
  }, []);

  const limparLoad = useCallback(() => {
    setLoad(null);
    salvar(CHAVE_LOAD, null);
  }, []);

  const definirTarifas = useCallback((valor: TarifasDoEstudo) => {
    setTarifas(valor);
    salvar(CHAVE_TARIFAS, valor);
  }, []);

  const limparTarifas = useCallback(() => {
    setTarifas(null);
    salvar(CHAVE_TARIFAS, null);
  }, []);

  const value = useMemo(
    () => ({ load, definirLoad, limparLoad, tarifas, definirTarifas, limparTarifas }),
    [load, definirLoad, limparLoad, tarifas, definirTarifas, limparTarifas],
  );
  return <EstudoContext.Provider value={value}>{children}</EstudoContext.Provider>;
}
