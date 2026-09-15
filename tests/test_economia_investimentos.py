"""Integração no tempo das economias de solar e BESS de ponta.

Até 15/09 o motor (herdado de .docs/motor_viabilidade.py) somava as 24 horas
do dia típico como se fossem o mês inteiro (solar) e contava um único ciclo
de BESS por mês. Estes testes travam a correção."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from motor_viabilidade.common import DIAS_NO_MES, DIAS_UTEIS_MES
from motor_viabilidade.InputBESSPonta import InputBESSPonta
from motor_viabilidade.InputGrid import InputGrid
from motor_viabilidade.InputSolarSCDEE import InputSolarSCDEE


def _solar(kw: float = 10.0) -> InputSolarSCDEE:
    perfil = [kw] * 24
    return InputSolarSCDEE(potencia_gerada_kw=[perfil] * 12, potencia_injetada_kw=[[-v for v in perfil]] * 12)


def test_dias_de_referencia():
    assert sum(DIAS_NO_MES) == 365
    assert sum(DIAS_UTEIS_MES) == 261


def test_energia_solar_do_mes_multiplica_o_dia_tipico_pelos_dias():
    s = _solar()
    assert s.energia_gerada_mensal_kwh() == [240.0 * d for d in DIAS_NO_MES]
    assert s.energia_injetada_mensal_kwh()[1] == 240.0 * 28


def test_economia_solar_limitada_ao_consumo_fora_ponta():
    s = _solar()
    grid = InputGrid(te_fp=0.2, tusd_fp=0.1, tusd_fio_b_fp=0.0)
    consumo = [1000.0] * 12  # bem menos que 240 × 30
    sem_limite = s.calcular_opex_energia_mensal(grid)
    com_limite = s.calcular_opex_energia_mensal(grid, consumo)
    assert sem_limite[0] == pytest.approx(-240 * 31 * 0.3)
    assert com_limite == [pytest.approx(-1000 * 0.3)] * 12


def test_bess_cicla_nos_dias_uteis_limitado_pela_ponta():
    b = InputBESSPonta(potencia_max_descarga_kw=100.0, energia_dod80_pos_pcs=1000.0, horas_ponta=3.0)
    # 100 kW × 3 h = 300 kWh/dia útil; consumo de ponta sobra em jan e falta em fev.
    energia_ponta = [10_000.0, 1_000.0] + [0.0] * 10
    descarga = b.energia_descarga_ponta_mensal_kwh(energia_ponta)
    assert descarga[0] == pytest.approx(300 * 23)
    assert descarga[1] == pytest.approx(1_000.0)
    assert descarga[2] == 0.0


def test_bess_energia_util_limita_o_ciclo_diario():
    b = InputBESSPonta(potencia_max_descarga_kw=500.0, energia_dod80_pos_pcs=900.0, horas_ponta=3.0)
    assert b.energia_descarga_ponta_mensal_kwh([1e9] * 12)[0] == pytest.approx(900 * 23)


def test_bess_saving_e_custo_de_recarga():
    b = InputBESSPonta(potencia_max_descarga_kw=100.0, energia_dod80_pos_pcs=1000.0, eta_total=0.9)
    grid = InputGrid(tusd_ponta=1.0, te_ponta=0.5, tusd_fp=0.2, te_fp=0.1)
    energia_ponta = [1_000.0] * 12
    assert b.calcular_saving_ponta(energia_ponta, grid) == pytest.approx(12_000 * 1.5)
    assert b.calcular_opex_fp_energia(energia_ponta, grid) == pytest.approx(12_000 / 0.9 * 0.3)


# ── Projeção anual ───────────────────────────────────────────────────────────

from motor_viabilidade.CalculadoraCF import CalculadoraCF  # noqa: E402
from motor_viabilidade.ParamsCF import ParamsCF  # noqa: E402


def test_degradacao_solar_reduz_a_economia_quando_a_geracao_nao_sobra():
    s = _solar(kw=1.0)  # 24 kWh/dia, bem abaixo do consumo
    s.degradacao_ano1, s.degradacao_demais = 0.02, 0.005
    grid = InputGrid(te_fp=0.2, tusd_fp=0.1, tusd_fio_b_fp=0.0)
    consumo = [1e9] * 12
    ano1 = -sum(s.calcular_opex_energia_mensal(grid, consumo, 1))
    ano3 = -sum(s.calcular_opex_energia_mensal(grid, consumo, 3))
    assert ano1 == pytest.approx(24 * 365 * 0.3 * 0.98)
    assert ano3 == pytest.approx(ano1 * 0.995 ** 2)


def test_fio_b_segue_o_cronograma_pelo_ano_de_operacao():
    s = _solar(kw=1.0)
    s.degradacao_ano1 = s.degradacao_demais = 0.0
    s.data_estudo_ano = 2025  # 45%; 2028 = 90%
    grid = InputGrid(te_fp=0.0, tusd_fp=1.0, tusd_fio_b_fp=1.0)
    ano1 = -sum(s.calcular_opex_energia_mensal(grid, None, 1))
    ano4 = -sum(s.calcular_opex_energia_mensal(grid, None, 4))
    assert ano1 == pytest.approx(24 * 365 * (1 - 0.45))
    assert ano4 == pytest.approx(24 * 365 * (1 - 0.90))


def test_capacidade_do_bess_cai_ate_o_eol_e_volta_na_reposicao():
    b = InputBESSPonta(percentual_eol=0.6, tempo_reposicao_anos=10)
    assert b.fator_capacidade(1) == 1.0
    assert b.fator_capacidade(4) == pytest.approx(1 - 0.4 * 3 / 9)
    assert b.fator_capacidade(10) == pytest.approx(0.6)  # último ano antes da reposição
    assert b.fator_capacidade(11) == 1.0  # reposto
    assert b.fator_capacidade(40) == pytest.approx(0.6)  # sem 2ª reposição: fica no EOL


def test_recarga_limita_a_descarga_diaria():
    b = InputBESSPonta(potencia_max_descarga_kw=500.0, energia_dod80_pos_pcs=5000.0,
                       potencia_max_carga_kw=100.0, tempo_carga_h=7.0, eta_total=0.9)
    assert b.energia_descarga_ponta_mensal_kwh([1e9] * 12)[0] == pytest.approx(100 * 7 * 0.9 * 23)


def test_serie_reajustada_e_cf_aceitam_valor_por_ano():
    calc = CalculadoraCF(ParamsCF(anos_projeto=3, reajuste_tarifa_ponta=0.1))
    serie = calc.serie_reajustada(lambda a: 100.0 * a, 0.1)
    assert serie == [pytest.approx(110.0), pytest.approx(242.0), pytest.approx(399.3)]
    cf = calc.cf_bess_ponta(capex=1, custo_reposicao=0, ano_reposicao=0,
                            opex_fp_carga=[1.0, 2.0, 3.0], saving_ponta=serie)
    assert cf["OPERATING_P_ENERGIA"] == [0.0, pytest.approx(110.0), pytest.approx(242.0), pytest.approx(399.3)]
    assert cf["OPERATING_FP_ENERGIA"] == [0.0, -1.0, -2.0, -3.0]
    with pytest.raises(ValueError):
        calc.cf_solar_scdee(capex=1, om=0, saving_fp_energia=[1.0], custo_troca_inv=0, ano_troca=0)
