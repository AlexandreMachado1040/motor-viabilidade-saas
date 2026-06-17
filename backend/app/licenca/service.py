"""
Ponte entre as licenças persistidas (DB) e o pacote do motor.

Constrói um ``motor_viabilidade.LicencaModulos`` a partir dos módulos ativos do
usuário, fechando o ciclo SaaS: o mesmo objeto de licença usado pelo motor de
cálculo é derivado da conta autenticada.
"""
from __future__ import annotations

from typing import Any

from ..db.models import MODULOS, User


def montar_licenca(user: User) -> Any:
    """
    Retorna uma instância de motor_viabilidade.LicencaModulos com as flags do
    usuário. Se o pacote do motor não estiver no PYTHONPATH, devolve um objeto
    simples (SimpleNamespace) com os mesmos atributos booleanos.
    """
    ativos = user.modulos_ativos
    flags = {m: (m in ativos) for m in MODULOS}
    try:
        from motor_viabilidade import LicencaModulos  # type: ignore
        return LicencaModulos(**flags)
    except Exception:
        from types import SimpleNamespace
        return SimpleNamespace(**flags)


def flags_licenca(user: User) -> dict[str, bool]:
    ativos = user.modulos_ativos
    return {m: (m in ativos) for m in MODULOS}
