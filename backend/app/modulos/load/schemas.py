"""Schemas do MOD 1 — InputLoad (memória de massa)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class InputLoadPayload(BaseModel):
    """Memória de massa: demanda mensal/horária + energia mensal ponta/fora-ponta."""
    demanda_maxima_kw: float | None = Field(
        default=None,
        description="Se ausente, é detectada como o pico da demanda.",
    )
    demanda_kw: list[list[float]] = Field(
        default_factory=list, description="Demanda por mês e hora (kW)."
    )
    energia_ponta_kwh: list[float] = Field(default_factory=list, description="12 meses.")
    energia_fp_kwh: list[float] = Field(default_factory=list, description="12 meses.")


class LoadResumo(BaseModel):
    """Resultado da validação + derivados do InputLoad."""
    valido: bool
    erros: list[str] = Field(default_factory=list)
    demanda_maxima_kw: float = 0.0
    energia_ponta_total: float = 0.0
    energia_fp_total: float = 0.0
    energia_total: float = 0.0
    energia_equivalente_kwh: list[float] = Field(default_factory=list)
    pico_mensal_kw: list[float] = Field(default_factory=list)
