import { createContext, useCallback, useMemo, useState, type ReactNode } from "react";
import type { InputLoadPayload, PicosMensais } from "../types";

// Dados de entrada do estudo compartilhados entre as páginas de módulo.
// O load (MOD 1) é carregado numa tela e consumido pelo simulador de tarifas
// (MOD 2) e pelo resumo (MOD 10). sessionStorage para sobreviver a um recarregamento da
// página sem vazar entre abas/sessões.
const CHAVE = "motor-viabilidade:estudo:load";

export interface LoadDoEstudo {
  payload: InputLoadPayload;
  fonte: string;
  picos?: PicosMensais;
}

interface EstudoState {
  load: LoadDoEstudo | null;
  definirLoad: (payload: InputLoadPayload, fonte: string, picos?: PicosMensais) => void;
  limparLoad: () => void;
}

export const EstudoContext = createContext<EstudoState | null>(null);

function lerSalvo(): LoadDoEstudo | null {
  try {
    const bruto = sessionStorage.getItem(CHAVE);
    return bruto ? (JSON.parse(bruto) as LoadDoEstudo) : null;
  } catch {
    return null;
  }
}

function salvar(valor: LoadDoEstudo | null): void {
  try {
    if (valor) sessionStorage.setItem(CHAVE, JSON.stringify(valor));
    else sessionStorage.removeItem(CHAVE);
  } catch {
    // armazenamento indisponível (modo privado, cota): segue só em memória
  }
}

export function EstudoProvider({ children }: { children: ReactNode }) {
  const [load, setLoad] = useState<LoadDoEstudo | null>(lerSalvo);

  const definirLoad = useCallback((payload: InputLoadPayload, fonte: string, picos?: PicosMensais) => {
    const valor: LoadDoEstudo = picos ? { payload, fonte, picos } : { payload, fonte };
    setLoad(valor);
    salvar(valor);
  }, []);

  const limparLoad = useCallback(() => {
    setLoad(null);
    salvar(null);
  }, []);

  const value = useMemo(() => ({ load, definirLoad, limparLoad }), [load, definirLoad, limparLoad]);
  return <EstudoContext.Provider value={value}>{children}</EstudoContext.Provider>;
}
