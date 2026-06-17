import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./useAuth";

interface Props {
  children: ReactNode;
  modulo?: string; // se informado, exige a licença do módulo
  apenasAdmin?: boolean; // se true, exige is_admin
}

export function ProtectedRoute({ children, modulo, apenasAdmin }: Props) {
  const { autenticado, carregando, temModulo, usuario } = useAuth();

  if (carregando) {
    return <div className="centro">Carregando sessão…</div>;
  }
  if (!autenticado) {
    return <Navigate to="/login" replace />;
  }
  if (apenasAdmin && !usuario?.is_admin) {
    return (
      <div className="centro">
        <h2>Acesso restrito</h2>
        <p>Esta área é exclusiva para administradores.</p>
      </div>
    );
  }
  if (modulo && !temModulo(modulo)) {
    return (
      <div className="centro">
        <h2>Acesso restrito</h2>
        <p>O módulo <b>{modulo}</b> não está contratado na sua licença.</p>
      </div>
    );
  }
  return <>{children}</>;
}
