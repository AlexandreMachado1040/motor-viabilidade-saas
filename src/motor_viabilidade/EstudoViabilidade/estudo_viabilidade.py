"""Orquestrador principal do estudo de viabilidade (módulo a módulo)."""
from __future__ import annotations

import json
import math
from dataclasses import replace
from typing import Optional

from ..common import log
from ..LicencaModulos import LicencaModulos
from ..ConfigAPIANEEL import ConfigAPIANEEL
from ..ClienteAPIANEEL import ClienteAPIANEEL
from ..InputLoad import InputLoad
from ..InputGrid import InputGrid
from ..InputSolarSCDEE import InputSolarSCDEE
from ..InputBESSPonta import InputBESSPonta
from ..InputGeradorPonta import InputGeradorPonta
from ..InputGeradorFormador import InputGeradorFormador
from ..InputBESSFormador import InputBESSFormador
from ..SolarHibridoParams import SolarHibridoParams
from ..InputNewGrid import InputNewGrid
from ..ParamsCF import ParamsCF
from ..CalculadoraOPEXGrid import CalculadoraOPEXGrid
from ..CalculadoraCF import CalculadoraCF
from ..IntegradorSolarimetrico import IntegradorSolarimetrico
from ..SimuladorTarifas import (
    InputSimuladorTarifas,
    ResultadoModalidade,
    opex_grid_da_fatura,
    simular_modalidade,
    tarifas_medias_consumo,
)
from ..InputGridZero import (
    AnaliseComparativaGridZero,
    InputGridZero,
    ResultadoGridZero,
)


class EstudoViabilidade:
    """
    Motor central do estudo de viabilidade híbrida.
    Ordem de execução:
      1.load → 2.grid → 3.solar → 4.bess_ponta → 5.gen_ponta →
      6.gen_form → 7.bess_form → 8.new_grid → 9.cf → 10.summary
      GZ.gridzero (independente, não requer Load)
    """

    def __init__(self, licenca: LicencaModulos):
        self.lic = licenca
        self.load:        Optional[InputLoad]           = None
        self.grid:        Optional[InputGrid]           = None
        self.solar:       Optional[InputSolarSCDEE]     = None
        self.bess_ponta:  Optional[InputBESSPonta]      = None
        self.gen_ponta:   Optional[InputGeradorPonta]   = None
        self.gen_form:    Optional[InputGeradorFormador] = None
        self.bess_form:   Optional[InputBESSFormador]   = None
        self.solar_bess:  Optional[SolarHibridoParams]  = None
        self.solar_gen:   Optional[SolarHibridoParams]  = None
        self.new_grid:    Optional[InputNewGrid]        = None
        self.params_cf:   ParamsCF = ParamsCF()
        # Fatura da modalidade escolhida no simulador de tarifas (opcional):
        # quando presente, substitui o OPEX simplificado de CalculadoraOPEXGrid.
        self.fatura_grid: Optional[tuple[ResultadoModalidade, InputSimuladorTarifas]] = None
        self._resultados: dict = {}

    # ── Carregamento ──────────────────────────────────────────────────
    def carregar_load(self, load: InputLoad):
        self.lic.requer("load")
        load.validar()
        self.load = load
        log.info(f"Load carregado: demanda máx = {load.demanda_maxima_kw} kW")

    def carregar_grid(self, grid: InputGrid, buscar_api: bool = False,
                      config_api: Optional[ConfigAPIANEEL] = None):
        self.lic.requer("grid")
        if buscar_api and config_api:
            cliente = ClienteAPIANEEL(config_api)
            dados_api = cliente.buscar_com_fallback(
                grid.concessionaria, grid.subgrupo, grid.modalidade, grid.ano_revisao)
            if dados_api:
                grid = InputGrid.de_api_aneel(dados_api)
                log.info("Tarifas atualizadas via API ANEEL.")
        self.grid = grid
        log.info(f"Grid carregado: {grid.concessionaria}/{grid.subgrupo}/"
                 f"{grid.modalidade}/{grid.ano_revisao}")

    def carregar_fatura_grid(self, entrada: InputSimuladorTarifas, modalidade: str):
        """Usa a fatura do simulador de tarifas como baseline da rede.

        O OPEX da rede passa a ser a fatura da modalidade (contratada,
        ultrapassagem e demanda por posto), e as tarifas de consumo do grid
        viram as médias anuais dessa modalidade — é o que solar, BESS e
        GridZero usam para calcular economia. Demais campos do grid
        (fio B, demanda de geração etc.) continuam os carregados.
        """
        self.lic.requer("grid")
        assert self.grid, "carregue o grid antes da fatura"
        resultado = simular_modalidade(entrada, modalidade)
        tarifa_ponta, tarifa_fp = tarifas_medias_consumo(resultado, entrada)
        self.grid = replace(
            self.grid, modalidade=resultado.modalidade,
            tusd_ponta=tarifa_ponta, te_ponta=0.0, tusd_fp=tarifa_fp, te_fp=0.0,
        )
        self.fatura_grid = (resultado, entrada)
        log.info(f"Fatura do simulador: {resultado.modalidade} · R$ {resultado.custo_anual:,.2f}/ano")

    def carregar_solar_scdee(self, solar: InputSolarSCDEE,
                              integrador: Optional[IntegradorSolarimetrico] = None):
        self.lic.requer("solar")
        if integrador and not solar.potencia_gerada_kw:
            solar.potencia_gerada_kw = integrador.gerar_matriz_potencia_12x24()
            solar.potencia_injetada_kw = [[-v for v in l] for l in solar.potencia_gerada_kw]
            solar.fonte_dados = integrador.fonte
        self.solar = solar
        log.info(f"Solar SCDEE: {solar.potencia_cc_kwp} kWp / "
                 f"{solar.modalidade_gd} / {solar.fonte_dados}")

    def carregar_bess_ponta(self, bess: InputBESSPonta):
        self.lic.requer("bess_ponta")
        self.bess_ponta = bess
        log.info(f"BESS Ponta: CAPEX R$ {bess.capex_r:,.0f}")

    def carregar_gen_ponta(self, gen: InputGeradorPonta):
        self.lic.requer("gen_ponta")
        self.gen_ponta = gen

    def carregar_gen_form(self, gen: InputGeradorFormador):
        self.lic.requer("gen_form")
        self.gen_form = gen

    def carregar_bess_form(self, bess: InputBESSFormador):
        self.lic.requer("bess_form")
        self.bess_form = bess

    def carregar_new_grid(self, ng: InputNewGrid):
        self.lic.requer("new_grid")
        ng.grid = ng.grid or self.grid
        self.new_grid = ng

    def configurar_cf(self, params: ParamsCF):
        self.lic.requer("cf")
        self.params_cf = params

    # ── OPEX Grid ─────────────────────────────────────────────────────
    def calcular_opex_grid(self) -> dict:
        assert self.load and self.grid
        if self.fatura_grid:
            return opex_grid_da_fatura(*self.fatura_grid)
        calc = CalculadoraOPEXGrid(self.load, self.grid)
        return {
            "mensal": {
                "tusd_ponta": calc.opex_tusd_ponta_mensal(),
                "tusd_fp":    calc.opex_tusd_fp_mensal(),
                "te_ponta":   calc.opex_te_ponta_mensal(),
                "te_fp":      calc.opex_te_fp_mensal(),
                "demanda_spt":calc.opex_demanda_spt_mensal(),
                "total":      calc.opex_grid_total_mensal(),
            },
            "anual": {
                "fp_energia": calc.opex_fp_energia_anual(),
                "p_energia":  calc.opex_p_energia_anual(),
                "fp_demanda": calc.opex_fp_demanda_anual(),
                "total":      calc.opex_grid_anual(),
            },
        }

    # ── OPEX Solar ────────────────────────────────────────────────────
    def calcular_opex_solar(self) -> dict:
        assert self.solar and self.grid
        opex_e = self.solar.calcular_opex_energia_mensal(self.grid)
        opex_d = self.solar.calcular_opex_demanda_mensal(self.grid)
        return {
            "mensal_energia": opex_e, "mensal_demanda": opex_d,
            "anual_energia": sum(opex_e), "anual_demanda": sum(opex_d),
            "capex": self.solar.capex_r, "om": self.solar.om_anual_r,
        }

    # ── Fluxo de Caixa ────────────────────────────────────────────────
    def calcular_cf(self) -> dict:
        self.lic.requer("cf")
        assert self.grid and self.load

        calc        = CalculadoraCF(self.params_cf)
        opex_g      = self.calcular_opex_grid()["anual"]
        cfs         = []
        capex_total = 0.0

        cf_g = calc.cf_grid(opex_g["fp_energia"], opex_g["p_energia"], opex_g["fp_demanda"])
        self._resultados["cf_grid"] = cf_g

        if self.solar and self.lic.solar:
            opex_s = self.calcular_opex_solar()
            cf_s = calc.cf_solar_scdee(
                capex=self.solar.capex_r, om=self.solar.om_anual_r,
                saving_fp_energia=-opex_s["anual_energia"],
                custo_troca_inv=self.solar.custo_troca_inversor_r,
                ano_troca=self.solar.ano_troca_inversor,
            )
            cfs.append(cf_s); capex_total += self.solar.capex_r
            self._resultados["cf_solar"] = cf_s

        if self.bess_ponta and self.lic.bess_ponta:
            opex_carga = self.bess_ponta.calcular_opex_fp_energia(
                self.load.demanda_kw, self.bess_ponta.potencia_max_carga_kw, self.grid)
            saving_p = self.bess_ponta.calcular_saving_ponta(self.load.demanda_kw, self.grid)
            cf_bp = calc.cf_bess_ponta(
                capex=self.bess_ponta.capex_r,
                custo_reposicao=self.bess_ponta.custo_reposicao_r,
                ano_reposicao=self.bess_ponta.tempo_reposicao_anos,
                opex_fp_carga=opex_carga, saving_ponta=saving_p,
            )
            cfs.append(cf_bp); capex_total += self.bess_ponta.capex_r
            self._resultados["cf_bess_ponta"] = cf_bp

        if self.gen_ponta and self.lic.gen_ponta:
            cf_gp = calc.cf_gen_ponta(
                capex=self.gen_ponta.capex_r, om=self.gen_ponta.om_anual_r,
                vida_util=self.gen_ponta.vida_util_anos,
                saving_ponta=opex_g["p_energia"],
            )
            cfs.append(cf_gp); capex_total += self.gen_ponta.capex_r
            self._resultados["cf_gen_ponta"] = cf_gp

        if self.new_grid and self.lic.new_grid:
            cf_ng = {
                "CAPITAL": [-self.new_grid.capex_r] + [0.0]*self.params_cf.anos_projeto,
                "REPLACEMENT": [0.0]*(self.params_cf.anos_projeto+1),
                "O&M": [0.0]*(self.params_cf.anos_projeto+1),
                "OPERATING_FP_ENERGIA": cf_g["OPERATING_FP_ENERGIA"],
                "OPERATING_P_ENERGIA":  cf_g["OPERATING_P_ENERGIA"],
                "OPERATING_FP_DEMANDA": cf_g["OPERATING_FP_DEMANDA"],
            }
            cfs.append(cf_ng); capex_total += self.new_grid.capex_r
            self._resultados["cf_new_grid"] = cf_ng

        baseline     = calc.totalizar_cf([cf_g])
        proposta     = calc.totalizar_cf(cfs) if cfs else [0.0]*(self.params_cf.anos_projeto+1)
        saving_serie = [p - b for p, b in zip(proposta, baseline)]
        fc_total     = [s + b for s, b in zip(saving_serie, baseline)]

        vpl     = calc.calcular_vpl(fc_total)
        tir     = calc.calcular_tir(fc_total)
        payback = calc.calcular_payback(fc_total)
        roi     = calc.calcular_roi(vpl, capex_total)

        resultados = {
            "baseline_nominal": baseline, "proposta_nominal": proposta,
            "saving_serie": saving_serie, "fc_total_nominal": fc_total,
            "fc_total_descontado": calc.descontar_serie(fc_total),
            "vpl": round(vpl, 2),
            "tir": round(tir*100, 4) if tir else None,
            "payback_anos": payback,
            "roi": round(roi, 4),
            "capex_total": capex_total,
            "viavel": tir is not None and tir > self.params_cf.taxa_desconto,
            "indicadores": {
                "taxa_desconto": self.params_cf.taxa_desconto,
                "inflacao": self.params_cf.inflacao,
                "anos_projeto": self.params_cf.anos_projeto,
                "taxa_desconto_real": self.params_cf.taxa_desconto_real,
            },
        }
        self._resultados["cf_consolidado"] = resultados
        return resultados

    # ── GridZero ──────────────────────────────────────────────────────
    def calcular_gridzero(
        self,
        gz: Optional[InputGridZero] = None,
        potencias_kw: Optional[list[float]] = None,
    ) -> dict[float, ResultadoGridZero]:
        """
        Executa análise GridZero.

        Parâmetros
        ----------
        gz : InputGridZero, opcional
            Se não fornecido, cria instância padrão com dados da planilha
            e tarifas do Grid carregado (se disponível).
        potencias_kw : list[float], opcional
            Potências AC a comparar. Padrão: [25, 50, 75, 100, 150] kW.

        Retorna
        -------
        dict {potencia_ac_kw: ResultadoGridZero}
        """
        self.lic.requer("gridzero")

        if gz is None:
            gz = InputGridZero()
            gz.carregar_demanda_horaria_planilha()
            # Herda tarifas do Grid carregado, se disponível
            if self.grid:
                gz.te_kwh   = self.grid.te_fp
                gz.tusd_kwh = self.grid.tusd_fp
                gz.preset_concessionaria = "manual"
                log.info("GridZero: tarifas herdadas do InputGrid carregado.")

        analise  = AnaliseComparativaGridZero(gz, potencias_kw)
        resultados = analise.rodar()
        self._resultados["gridzero"] = {
            str(kw): r.to_dict() for kw, r in resultados.items()
        }
        log.info(f"GridZero calculado para {len(resultados)} tamanhos de sistema.")
        return resultados

    # ── Sumário ───────────────────────────────────────────────────────
    def gerar_summary(self) -> dict:
        self.lic.requer("summary")
        cf    = self._resultados.get("cf_consolidado", {})
        opex_g = self.calcular_opex_grid()["anual"] if self.grid and self.load else {}
        gz_res = self._resultados.get("gridzero", {})

        return {
            "projeto": {
                "concessionaria":    self.grid.concessionaria if self.grid else None,
                "subgrupo":          self.grid.subgrupo if self.grid else None,
                "modalidade":        self.grid.modalidade if self.grid else None,
                "fonte_tarifas":     "simulador" if self.fatura_grid else "grid",
                "demanda_maxima_kw": self.load.demanda_maxima_kw if self.load else None,
                "potencia_solar_kwp":self.solar.potencia_cc_kwp if self.solar else None,
                "energia_bess_kwh":  self.bess_ponta.energia_dod80_kwh if self.bess_ponta else None,
            },
            "custos": {
                "opex_grid_anual": opex_g.get("total"),
                "capex_total":     cf.get("capex_total"),
            },
            "indicadores": {
                "vpl":     cf.get("vpl"),
                "tir_pct": cf.get("tir"),
                "payback": cf.get("payback_anos"),
                "roi":     cf.get("roi"),
                "viavel":  cf.get("viavel"),
            },
            "gridzero": gz_res,
            "modulos_ativos": {
                k: getattr(self.lic, k)
                for k in ["load", "grid", "solar", "bess_ponta", "gen_ponta",
                          "gen_form", "bess_form", "new_grid", "cf", "summary", "gridzero"]
            },
        }

    def para_json(self) -> str:
        def _clean(obj):
            if isinstance(obj, float):
                return None if math.isnan(obj) or math.isinf(obj) else obj
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_clean(v) for v in obj]
            return obj
        return json.dumps(_clean(self._resultados), ensure_ascii=False, indent=2)


__all__ = ["EstudoViabilidade"]
