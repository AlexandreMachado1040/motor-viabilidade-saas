"""Validação do MOD 7 — InputBESSFormador."""
from __future__ import annotations

from .schemas import BESSFormadorResumo, InputBESSFormadorPayload


def validar_bess_formador(p: InputBESSFormadorPayload) -> BESSFormadorResumo:
    # InputBESSFormador não tem `.validar()` nem propriedade/método derivado
    # (ao contrário de InputBESSPonta, que tem `energia_eol_dod80_kwh()`) —
    # só campos escalares já tipados pelo Pydantic.
    return BESSFormadorResumo(valido=True, erros=[])


__all__ = ["validar_bess_formador"]
