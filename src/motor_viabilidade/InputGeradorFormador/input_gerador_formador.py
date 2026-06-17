"""MOD 6 — Gerador formador de rede (grid-forming)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InputGeradorFormador:
    """Módulo 6 — Gerador formador de rede."""
    capex_r:            float = 60_000.0
    om_anual_r:         float = 600.0
    vida_util_anos:     int   = 5
    potencia_kw:        float = 250.0
    custo_diesel_litro: float = 5.92

    def custo_diesel_kwh(self) -> float:
        return 0.0


__all__ = ["InputGeradorFormador"]
