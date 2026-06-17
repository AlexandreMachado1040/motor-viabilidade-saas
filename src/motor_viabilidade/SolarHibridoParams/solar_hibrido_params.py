"""Parâmetros de geração solar para sistemas híbridos (BESS/GEN formadores)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SolarHibridoParams:
    """Parâmetros de geração solar para sistemas híbridos (BESS/GEN forming)."""
    potencia_cc_kwp:    float = 0.0
    capex_r:            float = 0.0
    om_anual_r:         float = 1500.0
    ano_troca_inversor: int   = 12
    custo_troca_inv_r:  float = 50000.0
    potencia_gerada_kw: list[list[float]] = field(default_factory=list)

    def energia_anual_kwh(self) -> float:
        return sum(sum(self.potencia_gerada_kw[m])
                   for m in range(len(self.potencia_gerada_kw)))


__all__ = ["SolarHibridoParams"]
