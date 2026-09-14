"""Schemas do MOD 5 — InputGeradorPonta (gerador diesel de ponta)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class InputGeradorPontaPayload(BaseModel):
    capex_r:            float = 60_000.0
    om_anual_r:         float = 600.0
    vida_util_anos:     int   = 5
    potencia_kw:        float = 250.0
    reserva_girante:    float = 1.0
    consumo_min_lh:     float = 0.0
    consumo_max_lh:     float = 0.0
    custo_diesel_litro: float = 5.92
    coef_interceptacao: float = 0.0
    slope:              float = 0.0


class GeradorPontaResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
    custo_diesel_kwh: float = 0.0
