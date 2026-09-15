import { Link } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { DEMO_MODE } from "../config";

// Módulos que já possuem front próprio (navegação privada).
const FRONTS: Record<string, string> = {
  load: "/modulos/load",
  summary: "/modulos/summary",
};

export function DashboardPage() {
  const { usuario, modulos, logout } = useAuth();

  return (
    <div className="dashboard">
      <header className="topbar">
        <div>
          <strong>Motor de Viabilidade</strong>
          <span className="muted"> · painel</span>
          {DEMO_MODE && <span className="tag-admin" style={{ marginLeft: 8 }}>modo demonstração</span>}
        </div>
        <div className="perfil">
          {usuario?.picture && <img src={usuario.picture} alt="" className="avatar" />}
          <span>{usuario?.name ?? usuario?.email}</span>
          {usuario?.is_admin && (
            <Link className="btn-link" to="/admin">
              Administração
            </Link>
          )}
          <button className="btn-link" onClick={() => void logout()}>
            Sair
          </button>
        </div>
      </header>

      <main>
        <h2>Módulos licenciados</h2>
        <p className="muted">
          Provedor: {usuario?.provider} · {usuario?.email}
        </p>
        <div className="grid-modulos">
          {Object.entries(modulos).map(([modulo, ativo]) => {
            const front = FRONTS[modulo];
            const conteudo = (
              <>
                <span className="dot" />
                {modulo}
                {front && ativo && <span className="seta">→</span>}
              </>
            );
            if (front && ativo) {
              return (
                <Link key={modulo} to={front} className="chip on link">
                  {conteudo}
                </Link>
              );
            }
            return (
              <div key={modulo} className={`chip ${ativo ? "on" : "off"}`}>
                {conteudo}
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}
