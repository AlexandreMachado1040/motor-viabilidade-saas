"""OPEX baseline da tarifa de rede (mensal/anual)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..InputLoad import InputLoad
    from ..InputGrid import InputGrid


class CalculadoraOPEXGrid:
    """Calcula o OPEX mensal/anual da tarifa de rede (baseline)."""

    def __init__(self, load: "InputLoad", grid: "InputGrid"):
        self.load = load
        self.grid = grid

    def opex_tusd_ponta_mensal(self) -> list[float]:
        return [e * self.grid.tusd_ponta for e in self.load.energia_ponta_kwh]

    def opex_tusd_fp_mensal(self) -> list[float]:
        return [e * self.grid.tusd_fp for e in self.load.energia_fp_kwh]

    def opex_te_ponta_mensal(self) -> list[float]:
        return [e * self.grid.te_ponta for e in self.load.energia_ponta_kwh]

    def opex_te_fp_mensal(self) -> list[float]:
        return [e * self.grid.te_fp for e in self.load.energia_fp_kwh]

    def opex_demanda_spt_mensal(self) -> list[float]:
        return [self.load.demanda_maxima_kw * self.grid.demanda_sem_posto] * 12

    def opex_grid_total_mensal(self) -> list[float]:
        return [a+b+c+d+e for a, b, c, d, e in zip(
            self.opex_tusd_ponta_mensal(), self.opex_tusd_fp_mensal(),
            self.opex_te_ponta_mensal(),   self.opex_te_fp_mensal(),
            self.opex_demanda_spt_mensal(),
        )]

    def opex_grid_anual(self) -> float:
        return sum(self.opex_grid_total_mensal())

    def opex_fp_energia_anual(self) -> float:
        return sum(self.opex_tusd_fp_mensal()) + sum(self.opex_te_fp_mensal())

    def opex_p_energia_anual(self) -> float:
        return sum(self.opex_tusd_ponta_mensal()) + sum(self.opex_te_ponta_mensal())

    def opex_fp_demanda_anual(self) -> float:
        return sum(self.opex_demanda_spt_mensal())


__all__ = ["CalculadoraOPEXGrid"]
