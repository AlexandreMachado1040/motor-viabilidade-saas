"""Parâmetros econômico-financeiros do fluxo de caixa (TMA, inflação, anos)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParamsCF:
    """Parâmetros econômico-financeiros do fluxo de caixa."""
    taxa_desconto:         float = 0.08
    inflacao:              float = 0.0393
    anos_projeto:          int   = 25
    reajuste_tarifa_ponta: float = 0.010
    reajuste_tarifa_fp:    float = 0.000
    reajuste_demanda_spt:  float = 0.008
    reajuste_combustivel:  float = 0.010

    @property
    def taxa_desconto_real(self) -> float:
        return ((1 + self.taxa_desconto) / (1 + self.inflacao)) - 1


__all__ = ["ParamsCF"]
