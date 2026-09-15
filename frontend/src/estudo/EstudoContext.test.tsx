import type { ContextType } from "react";
import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { AuthContext } from "../auth/AuthContext";
import { EstudoContext, EstudoProvider } from "./EstudoContext";

type AuthValue = NonNullable<ContextType<typeof AuthContext>>;
type EstudoValue = NonNullable<ContextType<typeof EstudoContext>>;

function auth(id: number | null): AuthValue {
  return {
    usuario: id === null ? null : { id, email: `u${id}@ex.com`, name: "U", picture: null, provider: "dev", is_active: true, is_admin: false },
    modulos: {}, carregando: false, autenticado: id !== null,
    login: () => {}, loginDev: async () => {}, logout: async () => {}, recarregar: async () => {},
    temModulo: () => true,
  } as AuthValue;
}

function montar() {
  const atual: { v: EstudoValue | null } = { v: null };
  const Leitor = () => (
    <EstudoContext.Consumer>{(v) => { atual.v = v; return null; }}</EstudoContext.Consumer>
  );
  const ui = (id: number | null) => (
    <AuthContext.Provider value={auth(id)}>
      <EstudoProvider><Leitor /></EstudoProvider>
    </AuthContext.Provider>
  );
  return { atual, ui };
}

beforeEach(() => sessionStorage.clear());

describe("EstudoProvider", () => {
  it("guarda por usuário e apaga os dados de quem sai", () => {
    const { atual, ui } = montar();
    const { rerender } = render(ui(1));
    act(() => atual.v!.definirInvestimento("cf", { taxa_desconto: 0.12 }));
    expect(sessionStorage.getItem("motor-viabilidade:estudo:investimentos:1")).toContain("0.12");

    rerender(ui(2)); // outra conta na mesma aba
    expect(atual.v!.investimentos).toEqual({});
    expect(sessionStorage.getItem("motor-viabilidade:estudo:investimentos:1")).toBeNull();

    rerender(ui(null)); // logout
    expect(atual.v!.investimentos).toEqual({});
  });

  it("recarregar a página com o mesmo usuário recupera o que ele salvou", () => {
    sessionStorage.setItem("motor-viabilidade:estudo:investimentos:7", JSON.stringify({ cf: { anos_projeto: 10 } }));
    sessionStorage.setItem("motor-viabilidade:estudo:investimentos", JSON.stringify({ cf: { anos_projeto: 99 } }));
    const { atual, ui } = montar();
    const { rerender } = render(ui(null)); // auth ainda carregando
    rerender(ui(7));
    expect(atual.v!.investimentos).toEqual({ cf: { anos_projeto: 10 } });
    expect(sessionStorage.getItem("motor-viabilidade:estudo:investimentos")).toBeNull(); // chave antiga sem dono
  });
});
