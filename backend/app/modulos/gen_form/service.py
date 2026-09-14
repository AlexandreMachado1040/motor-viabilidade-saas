"""Validação e cálculo de derivados do MOD 6 — InputGeradorFormador."""
from __future__ import annotations

from ...integracao.motor import get_input_gerador_formador_cls
from .schemas import GeradorFormadorResumo, InputGeradorFormadorPayload


def validar_gerador_formador(p: InputGeradorFormadorPayload) -> GeradorFormadorResumo:
    InputGeradorFormador = get_input_gerador_formador_cls()
    if InputGeradorFormador is not None:
        gerador = InputGeradorFormador(**p.model_dump())
        custo_diesel_kwh = gerador.custo_diesel_kwh()
    else:
        custo_diesel_kwh = 0.0

    return GeradorFormadorResumo(valido=True, erros=[], custo_diesel_kwh=custo_diesel_kwh)


__all__ = ["validar_gerador_formador"]
