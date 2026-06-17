"""MOD 3 — Sistema solar GD / compensação (SCDEE) + solarimetria integrada."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..InputGrid import InputGrid


@dataclass
class InputSolarSCDEE:
    """Módulo 3 — Sistema solar GD / compensação de energia elétrica."""
    estado:              str   = "São Paulo"
    potencia_ca_kw:      float = 211.27
    potencia_cc_kwp:     float = 300.0
    sobrecarga_inversor: float = 1.42
    capex_r:             float = 885000.0
    om_anual_r:          float = 1500.0
    degradacao_ano1:     float = 0.02
    degradacao_demais:   float = 0.0055
    custo_troca_inversor_r: float = 50000.0
    ano_troca_inversor:  int   = 12
    modalidade_gd:       str   = "GDIII"
    data_estudo_ano:     int   = 2024
    cronograma_transicao: dict = field(default_factory=lambda: {
        2023: 0.15, 2024: 0.30, 2025: 0.45, 2026: 0.60,
        2027: 0.75, 2028: 0.90,
    })
    tusd_ponta:          float = 1.326
    tusd_fp:             float = 0.118
    te_ponta:            float = 0.379
    te_fp:               float = 0.232
    tusd_fio_a_p:        float = 0.25728
    tusd_fio_b_p:        float = 1.130074
    outros_p:            float = 0.305195
    demanda_geracao_r:   float = 9.45
    potencia_gerada_kw:  list[list[float]] = field(default_factory=list)
    potencia_injetada_kw: list[list[float]] = field(default_factory=list)
    fonte_dados: str = "manual"
    dados_sonda: dict = field(default_factory=dict)
    dados_pvgis: dict = field(default_factory=dict)
    dados_tmy:   dict = field(default_factory=dict)

    @property
    def periodo_transicao_vigente(self) -> float:
        for a in sorted(self.cronograma_transicao.keys(), reverse=True):
            if self.data_estudo_ano >= a:
                return self.cronograma_transicao[a]
        return 0.0

    def energia_injetada_mensal_kwh(self) -> list[float]:
        return [abs(sum(self.potencia_injetada_kw[m]))
                if m < len(self.potencia_injetada_kw) else 0.0
                for m in range(12)]

    def energia_gerada_mensal_kwh(self) -> list[float]:
        return [sum(self.potencia_gerada_kw[m])
                if m < len(self.potencia_gerada_kw) else 0.0
                for m in range(12)]

    def calcular_opex_energia_mensal(self, grid: "InputGrid") -> list[float]:
        result = []
        energia_inj = self.energia_injetada_mensal_kwh()
        ft = self.periodo_transicao_vigente
        for m in range(12):
            e = energia_inj[m]
            economia = e * (grid.te_fp + grid.tusd_fp - ft * grid.tusd_fio_b_fp)
            result.append(-economia)
        return result

    def calcular_opex_demanda_mensal(self, grid: "InputGrid") -> list[float]:
        dem_red = self.potencia_ca_kw * grid.demanda_geracao / 12
        return [-dem_red] * 12


__all__ = ["InputSolarSCDEE"]
