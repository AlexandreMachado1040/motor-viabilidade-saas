"""MOD 5 — Gerador diesel de ponta."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InputGeradorPonta:
    """Módulo 5 — Gerador diesel de ponta."""
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

    def custo_diesel_kwh(self) -> float:
        if self.consumo_max_lh > 0 and self.potencia_kw > 0:
            return self.consumo_max_lh * self.custo_diesel_litro / self.potencia_kw
        return 0.0


__all__ = ["InputGeradorPonta"]
