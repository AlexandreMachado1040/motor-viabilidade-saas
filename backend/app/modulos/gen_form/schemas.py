"""Schemas do MOD 6 — InputGeradorFormador (gerador diesel formador de rede)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class InputGeradorFormadorPayload(BaseModel):
    capex_r:            float = 60_000.0
    om_anual_r:         float = 600.0
    vida_util_anos:     int   = 5
    potencia_kw:        float = 250.0
    custo_diesel_litro: float = 5.92


class GeradorFormadorResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
    # `InputGeradorFormador.custo_diesel_kwh()` sempre devolve 0.0 — formador
    # de rede é dimensionado por reserva/potência, não por consumo de
    # combustível medido (ao contrário do gerador de ponta, MOD 5); mantido
    # aqui só por simetria com gen_ponta, não porque o motor calcule algo.
    custo_diesel_kwh: float = 0.0
