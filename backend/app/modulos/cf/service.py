"""Validação e cálculo de derivados do MOD 9 — ParamsCF."""
from __future__ import annotations

from ...integracao.motor import get_params_cf_cls
from .schemas import ParamsCFPayload, ParamsCFResumo


def validar_params_cf(p: ParamsCFPayload) -> ParamsCFResumo:
    ParamsCF = get_params_cf_cls()
    if ParamsCF is not None:
        params = ParamsCF(**p.model_dump())
        taxa_real = params.taxa_desconto_real
    else:
        taxa_real = ((1 + p.taxa_desconto) / (1 + p.inflacao)) - 1

    return ParamsCFResumo(valido=True, erros=[], taxa_desconto_real=taxa_real)


__all__ = ["validar_params_cf"]
