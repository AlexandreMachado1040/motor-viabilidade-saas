import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { AdminUser } from "../types";

export function AdminPage() {
  const [usuarios, setUsuarios] = useState<AdminUser[]>([]);
  const [modulos, setModulos] = useState<string[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setCarregando(true);
    try {
      const [us, mods] = await Promise.all([
        api.get<AdminUser[]>("/admin/users"),
        api.get<string[]>("/admin/modulos"),
      ]);
      setUsuarios(us.data);
      setModulos(mods.data);
    } catch {
      setErro("Falha ao carregar usuários.");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const alternarModulo = (userId: number, modulo: string) => {
    setUsuarios((prev) =>
      prev.map((u) =>
        u.id === userId
          ? { ...u, modulos: { ...u.modulos, [modulo]: !u.modulos[modulo] } }
          : u,
      ),
    );
  };

  const salvar = async (user: AdminUser) => {
    setSalvando(user.id);
    setErro(null);
    try {
      const { data } = await api.put<AdminUser>(`/admin/users/${user.id}/modulos`, {
        modulos: user.modulos,
      });
      setUsuarios((prev) => prev.map((u) => (u.id === data.id ? data : u)));
    } catch {
      setErro("Falha ao salvar licenças.");
    } finally {
      setSalvando(null);
    }
  };

  if (carregando) return <div className="centro">Carregando…</div>;

  return (
    <div className="dashboard">
      <header className="topbar">
        <div>
          <strong>Administração</strong>
          <span className="muted"> · licenças por usuário</span>
        </div>
        <Link className="btn-link" to="/">
          ← Voltar
        </Link>
      </header>

      <main>
        {erro && <p className="aviso">{erro}</p>}
        <div className="tabela-wrap">
          <table className="tabela-admin">
            <thead>
              <tr>
                <th>Usuário</th>
                {modulos.map((m) => (
                  <th key={m} className="col-modulo">{m}</th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div className="cel-usuario">
                      <span>{u.name ?? u.email}</span>
                      <span className="muted">{u.email}</span>
                      {u.is_admin && <span className="tag-admin">admin</span>}
                    </div>
                  </td>
                  {modulos.map((m) => (
                    <td key={m} className="col-modulo">
                      <input
                        type="checkbox"
                        checked={u.modulos[m] ?? false}
                        onChange={() => alternarModulo(u.id, m)}
                      />
                    </td>
                  ))}
                  <td>
                    <button
                      className="btn btn-ms btn-sm"
                      disabled={salvando === u.id}
                      onClick={() => void salvar(u)}
                    >
                      {salvando === u.id ? "…" : "Salvar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
