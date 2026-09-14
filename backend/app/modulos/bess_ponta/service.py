"""Validação e cálculo de derivados do MOD 4 — InputBESSPonta."""
from __future__ import annotations

from ...integracao.motor import get_input_bess_ponta_cls
from .schemas import BESSPontaResumo, InputBESSPontaPayload


def validar_bess_ponta(p: InputBESSPontaPayload) -> BESSPontaResumo:
    InputBESSPonta = get_input_bess_ponta_cls()
    if InputBESSPonta is not None:
        bess = InputBESSPonta(**p.model_dump())
        energia_eol = bess.energia_eol_dod80_kwh()
    else:
        energia_eol = p.energia_dod80_kwh * p.percentual_eol

    return BESSPontaResumo(valido=True, erros=[], energia_eol_dod80_kwh=energia_eol)


__all__ = ["validar_bess_ponta"]
