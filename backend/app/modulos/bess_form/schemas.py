"""Schemas do MOD 7 — InputBESSFormador (bateria formadora de rede, off-grid/híbrido)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class InputBESSFormadorPayload(BaseModel):
    capex_r:              float = 5_560_000.0
    custo_reposicao_r:    float = 5_560_000.0
    tempo_reposicao_anos: int   = 14
    vida_util_anos:       int   = 14
    energia_dod80_kwh:    float = 0.0
    eta_total:            float = 0.961


class BESSFormadorResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
