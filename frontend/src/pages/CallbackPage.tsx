import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

/**
 * Página de retorno do OAuth. O backend já validou o login e gravou o cookie
 * de refresh; aqui apenas recarregamos a sessão e seguimos para o dashboard.
 */
export function CallbackPage() {
  const { recarregar } = useAuth();
  const navigate = useNavigate();
  const [erro, setErro] = useState(false);
  const rodou = useRef(false);

  useEffect(() => {
    if (rodou.current) return;
    rodou.current = true;

    const params = new URLSearchParams(window.location.search);
    if (params.get("login") !== "success") {
      setErro(true);
      return;
    }
    void recarregar().then(() => navigate("/", { replace: true }));
  }, [recarregar, navigate]);

  if (erro) {
    return (
      <div className="centro">
        <h2>Falha no login</h2>
        <a href="/login">Tentar novamente</a>
      </div>
    );
  }
  return <div className="centro">Concluindo autenticação…</div>;
}
