"""Validação e cálculo de derivados do MOD 5 — InputGeradorPonta."""
from __future__ import annotations

from ...integracao.motor import get_input_gerador_ponta_cls
from .schemas import GeradorPontaResumo, InputGeradorPontaPayload


def validar_gerador_ponta(p: InputGeradorPontaPayload) -> GeradorPontaResumo:
    InputGeradorPonta = get_input_gerador_ponta_cls()
    if InputGeradorPonta is not None:
        gerador = InputGeradorPonta(**p.model_dump())
        custo_diesel_kwh = gerador.custo_diesel_kwh()
    else:
        # Mesma fórmula de `custo_diesel_kwh()` no motor — fallback quando o
        # pacote motor_viabilidade não está disponível.
        custo_diesel_kwh = (
            p.consumo_max_lh * p.custo_diesel_litro / p.potencia_kw
            if p.consumo_max_lh > 0 and p.potencia_kw > 0 else 0.0
        )

    return GeradorPontaResumo(valido=True, erros=[], custo_diesel_kwh=custo_diesel_kwh)


__all__ = ["validar_gerador_ponta"]
