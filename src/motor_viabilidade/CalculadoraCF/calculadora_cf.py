"""Fluxo de caixa nominal/descontado, VPL, TIR, Payback e ROI (módulos 1–8)."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..ParamsCF import ParamsCF


class CalculadoraCF:
    """Gera o Fluxo de Caixa de cada módulo ao longo de anos."""

    def __init__(self, params: "ParamsCF"):
        self.p = params

    def _fator_reajuste(self, ano: int, taxa: float) -> float:
        return (1 + taxa) ** ano

    def _operacional(self, valor: "float | list[float]") -> list[float]:
        """Linha operacional [ano 0, 1..anos]: valor constante ou série anual.

        Série anual tem um valor por ano de operação (1..anos) — é como as
        economias entram com degradação, Fio B por ano e reajuste tarifário.
        """
        anos = self.p.anos_projeto
        if isinstance(valor, (int, float)):
            return [0.0] + [float(valor)] * anos
        if len(valor) != anos:
            raise ValueError(f"série anual deve ter {anos} anos (recebido: {len(valor)})")
        return [0.0] + [float(v) for v in valor]

    def serie_reajustada(self, valor_ano: "callable", taxa: float) -> list[float]:
        """[valor_ano(a) × (1+taxa)^a para a = 1..anos] — mesma convenção de cf_grid."""
        return [valor_ano(a) * self._fator_reajuste(a, taxa) for a in range(1, self.p.anos_projeto + 1)]

    def _descontar(self, valor: float, ano: int) -> float:
        if ano == 0:
            return valor
        return valor / (1 + self.p.taxa_desconto) ** ano

    def cf_grid(self, opex_fp_energia: float, opex_p_energia: float,
                opex_fp_demanda: float) -> dict:
        anos = self.p.anos_projeto
        cf = {
            "CAPITAL": [0.0]*(anos+1), "REPLACEMENT": [0.0]*(anos+1),
            "O&M": [0.0]*(anos+1), "OPERATING_FP_ENERGIA": [0.0],
            "OPERATING_P_ENERGIA": [0.0], "OPERATING_FP_DEMANDA": [0.0],
        }
        # Achado de auditoria (13/09): o ano 0 é o instante do investimento/
        # decisão — ainda não houve um ano de operação, então nenhuma linha
        # operacional (energia, demanda, O&M) pode ter valor no ano 0, nem
        # aqui nem em cf_solar_scdee/cf_bess_ponta/cf_gen_ponta (onde isso
        # duplicava um ano inteiro de economia sem desconto, superestimando
        # VPL/TIR e subestimando payback — ver dominios/financeiro-viabilidade-economica/spec.md).
        # A série do grid (baseline) precisa da MESMA convenção pra
        # `saving_serie`/`fc_total_nominal` (calcular_cf) ficarem consistentes.
        for a in range(1, anos+1):
            cf["OPERATING_FP_ENERGIA"].append(
                -opex_fp_energia * self._fator_reajuste(a, self.p.reajuste_tarifa_fp))
            cf["OPERATING_P_ENERGIA"].append(
                -opex_p_energia * self._fator_reajuste(a, self.p.reajuste_tarifa_ponta))
            cf["OPERATING_FP_DEMANDA"].append(
                -opex_fp_demanda * self._fator_reajuste(a, self.p.reajuste_demanda_spt))
        return cf

    def cf_solar_scdee(self, capex: float, om: float, saving_fp_energia: "float | list[float]",
                       custo_troca_inv: float, ano_troca: int) -> dict:
        anos = self.p.anos_projeto
        cf = {
            "CAPITAL": [-capex] + [0.0]*anos,
            "REPLACEMENT": [0.0]*(anos+1),
            # Ano 0 = só o CAPEX (achado de auditoria 13/09 — ver cf_grid acima).
            "O&M": [0.0] + [-om]*anos,
            "OPERATING_FP_ENERGIA": self._operacional(saving_fp_energia),
            "OPERATING_P_ENERGIA": [0.0]*(anos+1),
            "OPERATING_FP_DEMANDA": [0.0]*(anos+1),
        }
        if 0 < ano_troca <= anos:
            cf["REPLACEMENT"][ano_troca] = -custo_troca_inv
        return cf

    def cf_bess_ponta(self, capex: float, custo_reposicao: float, ano_reposicao: int,
                      opex_fp_carga: "float | list[float]", saving_ponta: "float | list[float]") -> dict:
        anos = self.p.anos_projeto
        cf = {
            "CAPITAL": [-capex] + [0.0]*anos,
            "REPLACEMENT": [0.0]*(anos+1),
            "O&M": [0.0]*(anos+1),
            # Ano 0 = só o CAPEX (achado de auditoria 13/09 — ver cf_grid acima).
            "OPERATING_FP_ENERGIA": [-v for v in self._operacional(opex_fp_carga)],
            "OPERATING_P_ENERGIA": self._operacional(saving_ponta),
            "OPERATING_FP_DEMANDA": [0.0]*(anos+1),
        }
        if 0 < ano_reposicao <= anos:
            cf["REPLACEMENT"][ano_reposicao] = -custo_reposicao
        return cf

    def cf_gen_ponta(self, capex: float, om: float, vida_util: int,
                     saving_ponta: float) -> dict:
        anos = self.p.anos_projeto
        cf = {
            "CAPITAL": [-capex] + [0.0]*anos,
            "REPLACEMENT": [0.0]*(anos+1),
            # Ano 0 = só o CAPEX (achado de auditoria 13/09 — ver cf_grid acima).
            "O&M": [0.0] + [-om]*anos,
            "OPERATING_FP_ENERGIA": [0.0]*(anos+1),
            "OPERATING_P_ENERGIA": [0.0] + [saving_ponta]*anos,
            "OPERATING_FP_DEMANDA": [0.0]*(anos+1),
        }
        for a in range(vida_util, anos+1, vida_util):
            cf["REPLACEMENT"][a] = -capex
        return cf

    def totalizar_cf(self, cfs: list[dict]) -> list[float]:
        anos = self.p.anos_projeto
        total = [0.0]*(anos+1)
        for cf in cfs:
            for linha in cf.values():
                for a, v in enumerate(linha):
                    if a <= anos:
                        total[a] += v
        return total

    def descontar_serie(self, serie: list[float]) -> list[float]:
        return [self._descontar(v, a) for a, v in enumerate(serie)]

    def calcular_vpl(self, serie_fc: list[float]) -> float:
        return sum(self.descontar_serie(serie_fc))

    def calcular_tir(self, serie_fc: list[float]) -> Optional[float]:
        def npv(r, s):
            try:
                return sum(v/(1+r)**t for t, v in enumerate(s))
            except (OverflowError, ZeroDivisionError):
                return float('inf')

        def dnpv(r, s):
            try:
                return sum(-t*v/(1+r)**(t+1) for t, v in enumerate(s) if t > 0)
            except (OverflowError, ZeroDivisionError):
                return 0.0
        # Precisamos de ao menos um fluxo positivo para existir TIR
        if not any(v > 0 for v in serie_fc):
            return None
        r = 0.10
        for _ in range(1000):
            f, df = npv(r, serie_fc), dnpv(r, serie_fc)
            if df == 0 or math.isnan(f) or math.isinf(f):
                return None
            r1 = r - f/df
            if abs(r1-r) < 1e-8:
                return r1 if -1 < r1 < 10 else None
            r = r1
            if not (-1 < r < 10):
                return None
        return None

    def calcular_payback(self, serie_fc: list[float]) -> Optional[int]:
        acum = 0.0
        for a, v in enumerate(serie_fc):
            acum += v
            if acum >= 0:
                return a
        return None

    def calcular_roi(self, vpl: float, investimento: float) -> float:
        return 0.0 if investimento == 0 else vpl / abs(investimento)


__all__ = ["CalculadoraCF"]
