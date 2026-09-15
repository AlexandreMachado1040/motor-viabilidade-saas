"""Orquestração do MOD 10 — Summary.

Roda o EstudoViabilidade completo: carrega load/grid (obrigatórios) + os
módulos de investimento enviados, configura o fluxo de caixa (params_cf),
chama calcular_cf() (popula o VPL/TIR/payback/ROI consolidado) e devolve
gerar_summary() — a mesma agregação que o motor já expõe, sem reimplementar
nada da regra de negócio aqui (igual ao princípio já seguido pelos módulos
1-9/11: esta camada só traduz HTTP↔motor).

Sem fallback quando motor_viabilidade está indisponível — orquestrar 8
módulos + fluxo de caixa fora do motor duplicaria a maior parte da regra de
negócio do pacote; mesma decisão já tomada pra gridzero."""
from __future__ import annotations

from ...integracao.motor import (
    get_estudo_viabilidade_cls,
    get_input_bess_formador_cls,
    get_input_bess_ponta_cls,
    get_input_gerador_formador_cls,
    get_input_gerador_ponta_cls,
    get_input_grid_cls,
    get_input_load_cls,
    get_input_new_grid_cls,
    get_input_solar_scdee_cls,
    get_licenca_modulos_cls,
    get_params_cf_cls,
    get_simulador_tarifas_mod,
)
from ..grid.tarifas_service import montar_entrada
from ..load.service import _validar_estrutura as validar_estrutura_load
from .schemas import SummaryPayload, SummaryResumo


def validar_summary(p: SummaryPayload) -> SummaryResumo | None:
    """Devolve `None` quando o motor está indisponível (router converte pra 503)."""
    erros = validar_estrutura_load(p.load)
    if erros:
        return SummaryResumo(valido=False, erros=erros)

    EstudoViabilidade = get_estudo_viabilidade_cls()
    LicencaModulos = get_licenca_modulos_cls()
    InputLoad = get_input_load_cls()
    InputGrid = get_input_grid_cls()
    if not all([EstudoViabilidade, LicencaModulos, InputLoad, InputGrid]):
        return None

    # Licença interna do motor (LicencaModulos) reflete exatamente quais
    # módulos opcionais vieram no payload — não a licença HTTP do usuário
    # (essa já foi checada por require_module("summary") no router; o motor
    # também confere lic.requer(modulo) a cada carregar_*, então precisa
    # bater com o que de fato estamos carregando, ou levantaria PermissionError).
    lic = LicencaModulos(
        load=True, grid=True, cf=True, summary=True,
        solar=p.solar is not None,
        bess_ponta=p.bess_ponta is not None,
        gen_ponta=p.gen_ponta is not None,
        gen_form=p.gen_form is not None,
        bess_form=p.bess_form is not None,
        new_grid=p.new_grid is not None,
        gridzero=False,
    )
    estudo = EstudoViabilidade(lic)
    estudo.carregar_load(InputLoad(**p.load.model_dump()))
    estudo.carregar_grid(InputGrid(**p.grid.model_dump()))

    if p.tarifas is not None and p.modalidade is not None:
        mod_tarifas = get_simulador_tarifas_mod()
        if mod_tarifas is None:
            return None
        entrada = montar_entrada(mod_tarifas, p.tarifas)
        erros = entrada.validar()
        if erros:
            return SummaryResumo(valido=False, erros=erros)
        try:
            estudo.carregar_fatura_grid(entrada, p.modalidade)
        except ValueError as e:  # modalidade sem tarifa informada
            return SummaryResumo(valido=False, erros=[str(e)])

    ParamsCF = get_params_cf_cls()
    if ParamsCF is not None:
        estudo.configurar_cf(ParamsCF(**p.params_cf.model_dump()))

    if p.solar is not None:
        InputSolarSCDEE = get_input_solar_scdee_cls()
        if InputSolarSCDEE is not None:
            estudo.carregar_solar_scdee(InputSolarSCDEE(**p.solar.model_dump()))

    if p.bess_ponta is not None:
        InputBESSPonta = get_input_bess_ponta_cls()
        if InputBESSPonta is not None:
            estudo.carregar_bess_ponta(InputBESSPonta(**p.bess_ponta.model_dump()))

    if p.gen_ponta is not None:
        InputGeradorPonta = get_input_gerador_ponta_cls()
        if InputGeradorPonta is not None:
            estudo.carregar_gen_ponta(InputGeradorPonta(**p.gen_ponta.model_dump()))

    if p.gen_form is not None:
        InputGeradorFormador = get_input_gerador_formador_cls()
        if InputGeradorFormador is not None:
            estudo.carregar_gen_form(InputGeradorFormador(**p.gen_form.model_dump()))

    if p.bess_form is not None:
        InputBESSFormador = get_input_bess_formador_cls()
        if InputBESSFormador is not None:
            estudo.carregar_bess_form(InputBESSFormador(**p.bess_form.model_dump()))

    if p.new_grid is not None:
        InputNewGrid = get_input_new_grid_cls()
        if InputNewGrid is not None:
            estudo.carregar_new_grid(InputNewGrid(**p.new_grid.model_dump()))

    estudo.calcular_cf()
    resumo = estudo.gerar_summary()
    # `resumo["gridzero"]` fica de fora do schema de propósito — GridZero é
    # independente (não passa por load/grid) e já tem seu próprio endpoint
    # (/modulos/gridzero/validar); aqui ele sempre viria vazio ({}), já que
    # não chamamos calcular_gridzero() neste fluxo.

    return SummaryResumo(
        valido=True, erros=[],
        projeto=resumo["projeto"],
        custos=resumo["custos"],
        indicadores=resumo["indicadores"],
        modulos_ativos=resumo["modulos_ativos"],
    )


__all__ = ["validar_summary"]
