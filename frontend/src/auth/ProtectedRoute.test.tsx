import type { ContextType, ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuthContext } from "./AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";
import type { Usuario } from "../types";

type AuthValue = NonNullable<ContextType<typeof AuthContext>>;

function criarUsuario(over: Partial<Usuario> = {}): Usuario {
  return {
    id: 1,
    email: "yuri@empresa.com",
    name: "Yuri",
    picture: null,
    provider: "microsoft",
    is_active: true,
    is_admin: false,
    ...over,
  };
}

function criarAuth(over: Partial<AuthValue> = {}): AuthValue {
  return {
    usuario: null,
    modulos: {},
    carregando: false,
    autenticado: false,
    login: () => {},
    loginDev: async () => {},
    logout: async () => {},
    recarregar: async () => {},
    temModulo: (_m: string) => false,
    ...over,
  };
}

function renderRota(
  auth: AuthValue,
  children: ReactNode,
  props: { modulo?: string; apenasAdmin?: boolean } = {},
) {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/login" element={<div>Tela de Login</div>} />
          <Route
            path="/"
            element={
              <ProtectedRoute modulo={props.modulo} apenasAdmin={props.apenasAdmin}>
                {children}
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("ProtectedRoute", () => {
  it("mostra carregando enquanto a sessão é resolvida", () => {
    renderRota(criarAuth({ carregando: true }), <div>Conteúdo</div>);
    expect(screen.getByText(/Carregando sessão/)).toBeInTheDocument();
  });

  it("redireciona para /login quando não autenticado", () => {
    renderRota(criarAuth({ autenticado: false }), <div>Conteúdo</div>);
    expect(screen.getByText("Tela de Login")).toBeInTheDocument();
  });

  it("renderiza o conteúdo quando autenticado", () => {
    renderRota(
      criarAuth({ autenticado: true, usuario: criarUsuario() }),
      <div>Conteúdo Secreto</div>,
    );
    expect(screen.getByText("Conteúdo Secreto")).toBeInTheDocument();
  });

  it("bloqueia área admin para usuário comum", () => {
    renderRota(
      criarAuth({ autenticado: true, usuario: criarUsuario({ is_admin: false }) }),
      <div>Painel Admin</div>,
      { apenasAdmin: true },
    );
    expect(screen.getByText(/exclusiva para administradores/)).toBeInTheDocument();
    expect(screen.queryByText("Painel Admin")).not.toBeInTheDocument();
  });

  it("libera área admin para administrador", () => {
    renderRota(
      criarAuth({ autenticado: true, usuario: criarUsuario({ is_admin: true }) }),
      <div>Painel Admin</div>,
      { apenasAdmin: true },
    );
    expect(screen.getByText("Painel Admin")).toBeInTheDocument();
  });

  it("bloqueia quando o módulo não está licenciado", () => {
    renderRota(
      criarAuth({
        autenticado: true,
        usuario: criarUsuario(),
        temModulo: (_m: string) => false,
      }),
      <div>GridZero</div>,
      { modulo: "gridzero" },
    );
    expect(screen.getByText(/não está contratado/)).toBeInTheDocument();
    expect(screen.queryByText("GridZero")).not.toBeInTheDocument();
  });

  it("libera quando o módulo está licenciado", () => {
    renderRota(
      criarAuth({
        autenticado: true,
        usuario: criarUsuario(),
        temModulo: (m: string) => m === "gridzero",
      }),
      <div>GridZero</div>,
      { modulo: "gridzero" },
    );
    expect(screen.getByText("GridZero")).toBeInTheDocument();
  });
});
