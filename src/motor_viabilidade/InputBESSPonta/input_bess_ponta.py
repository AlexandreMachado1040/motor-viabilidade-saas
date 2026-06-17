"""MOD 4 — Bateria (BESS) para redução de demanda na ponta."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..InputGrid import InputGrid


@dataclass
class InputBESSPonta:
    """Módulo 4 — Bateria para redução de ponta."""
    capex_r:                 float = 5_526_000.0
    custo_reposicao_r:       float = 5_526_000.0
    tempo_reposicao_anos:    int   = 14
    vida_util_anos:          int   = 14
    percentual_eol:          float = 0.60
    n_ciclos_dod80:          float = 4882.5
    n_ciclos_dod100:         float = 3906.0
    dod_operacional:         float = 0.80
    n_bms_por_br:            int   = 18
    n_bms_total:             int   = 180
    n_brs:                   int   = 10
    brs_serie:               int   = 1
    brs_paralelo:            int   = 10
    tensao_nominal_v:        float = 691.2
    resistencia_interna_mohm: float = 43.2
    coulombic_eff:           float = 0.953
    tensao_corte_carga_v:    float = 777.6
    tensao_corte_descarga_v: float = 583.2
    capacidade_c10_ah:       float = 2890.0
    corrente_max_carga_a:    float = 330.0
    corrente_max_descarga_a: float = 330.0
    potencia_max_carga_kw:   float = 228.096
    potencia_max_descarga_kw: float = 228.096
    perda_sistema:           float = 0.0115
    eta_pcs:                 float = 0.982
    eta_bateria:             float = 0.9885
    eta_sys:                 float = 0.99
    eta_total:               float = 0.961
    energia_dod80_kwh:       float = 1598.05
    energia_dod100_kwh:      float = 1997.57
    energia_dod80_pos_pcs:   float = 1535.73
    energia_dod100_pos_pcs:  float = 1919.66
    tempo_carga_h:           float = 7.006
    tempo_descarga_h:        float = 7.006

    def energia_eol_dod80_kwh(self) -> float:
        return self.energia_dod80_kwh * self.percentual_eol

    def calcular_opex_fp_energia(
        self, demanda_kw: list[list[float]], potencia_max_kw: float, grid: "InputGrid"
    ) -> float:
        total = 0.0
        for m in range(12):
            energia_carga = potencia_max_kw * self.tempo_carga_h / self.eta_total
            total += energia_carga * grid.tarifa_fp
        return total

    def calcular_saving_ponta(self, demanda_kw: list[list[float]], grid: "InputGrid") -> float:
        total = 0.0
        for m in range(12):
            energia_descarga = self.potencia_max_descarga_kw * self.tempo_descarga_h
            total += energia_descarga * grid.tarifa_ponta
        return total


__all__ = ["InputBESSPonta"]
