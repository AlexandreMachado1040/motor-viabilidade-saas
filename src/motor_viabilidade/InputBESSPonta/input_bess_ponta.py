"""MOD 4 — Bateria (BESS) para redução de demanda na ponta."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..common import DIAS_UTEIS_MES

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
    horas_ponta:             float = 3.0

    def energia_eol_dod80_kwh(self) -> float:
        return self.energia_dod80_kwh * self.percentual_eol

    def fator_capacidade(self, ano_operacao: int) -> float:
        """Capacidade útil no ano, relativa à nova.

        Queda linear de 100% no 1º ano até ``percentual_eol`` no último ano
        antes da reposição (ano ``tempo_reposicao_anos``); a reposição devolve
        100% no ano seguinte. Uma reposição só,
        como em CalculadoraCF.cf_bess_ponta — depois dela a capacidade não
        volta a ser renovada.
        """
        if ano_operacao < 1 or self.tempo_reposicao_anos <= 0:
            return 1.0
        idade = ano_operacao - 1
        if ano_operacao > self.tempo_reposicao_anos:
            idade -= self.tempo_reposicao_anos
        passos = max(self.tempo_reposicao_anos - 1, 1)
        queda = (1 - self.percentual_eol) * min(idade, passos) / passos
        return max(self.percentual_eol, 1 - queda)

    def energia_descarga_ponta_mensal_kwh(
        self, energia_ponta_kwh: list[float], ano_operacao: int = 0,
    ) -> list[float]:
        """Energia que o BESS abate na ponta, por mês.

        Um ciclo por dia útil, limitado pelo que cabe no posto (potência ×
        horas de ponta), pela energia útil após o PCS (degradada no ano), pelo
        que dá para recarregar (potência de carga × tempo de carga × eficiência)
        e pelo consumo de ponta do mês — o BESS não descarrega mais do que a
        carga consome na ponta. Até 15/09 o motor contava um único ciclo por
        mês, sem nenhum desses limites.
        """
        por_dia = min(
            self.potencia_max_descarga_kw * self.horas_ponta,
            self.energia_dod80_pos_pcs * self.fator_capacidade(ano_operacao),
            self.potencia_max_carga_kw * self.tempo_carga_h * self.eta_total,
        )
        return [min(por_dia * DIAS_UTEIS_MES[m], energia_ponta_kwh[m]) for m in range(12)]

    def calcular_opex_fp_energia(
        self, energia_ponta_kwh: list[float], grid: "InputGrid", ano_operacao: int = 0,
    ) -> float:
        """Custo anual de recarregar fora ponta o que foi descarregado (com perdas)."""
        return sum(e / self.eta_total * grid.tarifa_fp
                   for e in self.energia_descarga_ponta_mensal_kwh(energia_ponta_kwh, ano_operacao))

    def calcular_saving_ponta(
        self, energia_ponta_kwh: list[float], grid: "InputGrid", ano_operacao: int = 0,
    ) -> float:
        """Economia anual de energia na ponta (TUSD + TE ponta), sem reajuste."""
        return sum(e * grid.tarifa_ponta
                   for e in self.energia_descarga_ponta_mensal_kwh(energia_ponta_kwh, ano_operacao))


__all__ = ["InputBESSPonta"]
