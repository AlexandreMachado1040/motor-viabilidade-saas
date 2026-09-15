"""MOD 3 — Sistema solar GD / compensação (SCDEE) + solarimetria integrada."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..common import DIAS_NO_MES

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
        return self.fracao_transicao(self.data_estudo_ano)

    def fracao_transicao(self, ano_calendario: int) -> float:
        """Fração do Fio B não compensada no ano (cronograma da Lei 14.300)."""
        for a in sorted(self.cronograma_transicao.keys(), reverse=True):
            if ano_calendario >= a:
                return self.cronograma_transicao[a]
        return 0.0

    def fator_degradacao(self, ano_operacao: int) -> float:
        """Fração da geração inicial no ano de operação (1 = primeiro ano)."""
        if ano_operacao < 1:
            return 1.0
        return (1 - self.degradacao_ano1) * (1 - self.degradacao_demais) ** (ano_operacao - 1)

    # A matriz 12×24 é o dia típico do mês (kW médio por hora): o mês é a
    # soma das 24 horas × dias do mês. Até 15/09 o motor (e o legado em
    # .docs/) devolvia só a soma das 24 horas — 1 dia por mês.
    def energia_injetada_mensal_kwh(self) -> list[float]:
        return [abs(sum(self.potencia_injetada_kw[m])) * DIAS_NO_MES[m]
                if m < len(self.potencia_injetada_kw) else 0.0
                for m in range(12)]

    def energia_gerada_mensal_kwh(self) -> list[float]:
        return [sum(self.potencia_gerada_kw[m]) * DIAS_NO_MES[m]
                if m < len(self.potencia_gerada_kw) else 0.0
                for m in range(12)]

    def calcular_opex_energia_mensal(
        self, grid: "InputGrid", consumo_fp_kwh: Optional[list[float]] = None,
        ano_operacao: int = 0,
    ) -> list[float]:
        """Economia mensal (negativa) da energia compensada, sem reajuste tarifário.

        Com ``consumo_fp_kwh``, a compensação do mês fica limitada ao consumo
        fora ponta: crédito além disso não reduz a fatura do mês (vira saldo
        para meses seguintes, que o motor não modela). ``ano_operacao`` ≥ 1
        aplica a degradação daquele ano e o Fio B do ano-calendário
        correspondente (o ano 1 é ``data_estudo_ano``); 0 = geração nominal.
        """
        result = []
        fator = self.fator_degradacao(ano_operacao)
        energia_inj = [e * fator for e in self.energia_injetada_mensal_kwh()]
        ano_cal = self.data_estudo_ano + max(ano_operacao, 1) - 1
        ft = self.fracao_transicao(ano_cal)
        for m in range(12):
            e = energia_inj[m]
            if consumo_fp_kwh is not None:
                e = min(e, consumo_fp_kwh[m])
            economia = e * (grid.te_fp + grid.tusd_fp - ft * grid.tusd_fio_b_fp)
            result.append(-economia)
        return result

    def calcular_opex_demanda_mensal(self, grid: "InputGrid") -> list[float]:
        dem_red = self.potencia_ca_kw * grid.demanda_geracao / 12
        return [-dem_red] * 12


__all__ = ["InputSolarSCDEE"]
