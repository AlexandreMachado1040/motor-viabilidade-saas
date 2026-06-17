import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/useAuth";

interface Provedores {
  google: boolean;
  microsoft: boolean;
  dev: boolean;
}

export function LoginPage() {
  const { autenticado, carregando, login, loginDev } = useAuth();
  const [provedores, setProvedores] = useState<Provedores>({
    google: false,
    microsoft: false,
    dev: false,
  });
  const [emailDev, setEmailDev] = useState("alexandreclm@gmail.com");
  const [erroDev, setErroDev] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Provedores>("/auth/providers")
      .then(({ data }) => setProvedores(data))
      .catch(() => setProvedores({ google: true, microsoft: true, dev: false }));
  }, []);

  const entrarDev = async () => {
    setErroDev(null);
    try {
      await loginDev(emailDev);
    } catch {
      setErroDev("Falha no login de desenvolvimento.");
    }
  };

  if (!carregando && autenticado) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="centro">
      <div className="card-login">
        <h1>Motor de Viabilidade</h1>
        <p className="muted">Acesse com sua conta corporativa</p>

        <button
          className="btn btn-ms"
          disabled={!provedores.microsoft}
          onClick={() => login("microsoft")}
        >
          Entrar com Microsoft
        </button>
        <button
          className="btn btn-google"
          disabled={!provedores.google}
          onClick={() => login("google")}
        >
          Entrar com Google
        </button>

        {!provedores.google && !provedores.microsoft && (
          <p className="aviso">
            Nenhum provedor OAuth configurado. Defina as credenciais no
            <code> backend/.env</code>.
          </p>
        )}

        {provedores.dev && (
          <div className="dev-box">
            <div className="muted">Modo desenvolvedor (sem OAuth)</div>
            <input
              type="email"
              value={emailDev}
              onChange={(e) => setEmailDev(e.target.value)}
              placeholder="email@exemplo.com"
            />
            <button className="btn btn-dev" onClick={() => void entrarDev()}>
              Entrar (dev)
            </button>
            {erroDev && <p className="aviso">{erroDev}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
