import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshAccessToken, setAccessToken } from "../api/client";
import type { MeResponse, ModuloFlags, Provedor, Usuario } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface AuthState {
  usuario: Usuario | null;
  modulos: ModuloFlags;
  carregando: boolean;
  autenticado: boolean;
  login: (provedor: Provedor) => void;
  loginDev: (email: string) => Promise<void>;
  logout: () => Promise<void>;
  recarregar: () => Promise<void>;
  temModulo: (modulo: string) => boolean;
}

export const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [modulos, setModulos] = useState<ModuloFlags>({});
  const [carregando, setCarregando] = useState(true);

  const carregarSessao = useCallback(async () => {
    setCarregando(true);
    const token = await refreshAccessToken();
    if (!token) {
      setUsuario(null);
      setModulos({});
      setCarregando(false);
      return;
    }
    try {
      const { data } = await api.get<MeResponse>("/auth/me");
      setUsuario(data.usuario);
      setModulos(data.modulos);
    } catch {
      setUsuario(null);
      setModulos({});
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void carregarSessao();
  }, [carregarSessao]);

  const login = useCallback((provedor: Provedor) => {
    // Redireciona o navegador ao backend, que inicia o fluxo OAuth.
    window.location.href = `${API_URL}/auth/login/${provedor}`;
  }, []);

  const loginDev = useCallback(
    async (email: string) => {
      // Login de desenvolvimento (sem OAuth). Requer DEV_LOGIN_ENABLED no backend.
      await api.post("/auth/dev-login", { email });
      await carregarSessao();
    },
    [carregarSessao],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAccessToken(null);
      setUsuario(null);
      setModulos({});
    }
  }, []);

  const temModulo = useCallback((modulo: string) => modulos[modulo] === true, [modulos]);

  const value = useMemo<AuthState>(
    () => ({
      usuario,
      modulos,
      carregando,
      autenticado: usuario !== null,
      login,
      loginDev,
      logout,
      recarregar: carregarSessao,
      temModulo,
    }),
    [usuario, modulos, carregando, login, loginDev, logout, carregarSessao, temModulo],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
