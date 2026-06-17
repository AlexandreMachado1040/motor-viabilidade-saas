"""MOD 7 — BESS formador de rede (off-grid / híbrido, grid-forming)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InputBESSFormador:
    """Módulo 7 — BESS formador de rede (off-grid / híbrido)."""
    capex_r:              float = 5_560_000.0
    custo_reposicao_r:    float = 5_560_000.0
    tempo_reposicao_anos: int   = 14
    vida_util_anos:       int   = 14
    energia_dod80_kwh:    float = 0.0
    eta_total:            float = 0.961


__all__ = ["InputBESSFormador"]
