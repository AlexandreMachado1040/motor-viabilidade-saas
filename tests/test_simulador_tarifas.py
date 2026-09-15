"""Testes do simulador de modalidades tarifárias (MOD 2).

Os valores de referência saem da aba "Simulação anual" da planilha
SIMULADOR TARIFAS ANUAL_V1.xls — componente a componente, porque a planilha
tem meses em branco e o total dela não é reproduzível por inteiro.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from motor_viabilidade.SimuladorTarifas import (
    InputSimuladorTarifas,
    SimuladorTarifas,
    TarifasAzul,
    TarifasBaixaTensao,
    TarifasConvencional,
    TarifasVerde,
    exemplo_simulador_tarifas,
)

ZERO = [0.0] * 12


def _entrada(**kw) -> InputSimuladorTarifas:
    base = dict(
        demanda_ponta_kw=list(ZERO), demanda_fp_kw=list(ZERO),
        consumo_ponta_kwh=list(ZERO), consumo_fp_kwh=list(ZERO),
    )
    base.update(kw)
    return InputSimuladorTarifas(**base)


def test_convencional_reproduz_linhas_da_planilha():
    # Linha 4/5 (demanda única e ultrapassagem) e linha 6 (consumo) da planilha.
    medidas = [60.0, 60.0, 74.0952, 90.2328, 60.0, 60.9342, 62.1888, 69.1752, 66.2232, 65.7312, 68.6832, 0.0]
    consumo = [17458.42, 19500.07, 18395.01, 20083.98, 16082.09, 0.0, 18601.65, 17716.37,
               18626.08, 17701.69, 21217.86, 0.0]
    e = _entrada(demanda_fp_kw=medidas, consumo_fp_kwh=consumo,
                 convencional=TarifasConvencional(demanda=30.53, consumo=0.3242))
    r = SimuladorTarifas(e).convencional()
    # A planilha deixa dezembro em branco (0 × tarifa); aqui dezembro fatura a
    # contratada (60 kW), como manda a regra de demanda faturável.
    assert r.componentes["Demanda"] == pytest.approx(22508.663 + 60 * 30.53, abs=0.01)
    assert r.componentes["Ultrapassagem"] == pytest.approx(4527.0372, abs=0.01)
    assert r.componentes["Consumo"] == pytest.approx(60101.239 + 0.3242 * (sum(consumo) - 185383.22), abs=0.5)
    assert r.meses_com_ultrapassagem == 6  # 60,93 e 62,19 ficam dentro dos 5%


def test_azul_ultrapassagem_por_posto_como_na_planilha():
    ponta = [60.0, 60.0, 60.0, 60.024, 60.0, 60.0, 60.0, 69.1752, 66.2232, 60.0, 68.6832, 60.0]
    fp = [60.0, 69.7656, 74.0952, 90.2328, 60.0, 60.0, 62.1888, 60.0, 61.6968, 60.0, 67.9944, 60.0]
    e = _entrada(demanda_ponta_kw=ponta, demanda_fp_kw=fp,
                 azul=TarifasAzul(demanda_ponta=28.41, demanda_fp=10.07, consumo_ponta=0.44734, consumo_fp=0.31))
    r = SimuladorTarifas(e).azul()
    assert r.componentes["Ultrapassagem ponta"] == pytest.approx(1368.3165, abs=0.01)
    assert r.componentes["Ultrapassagem fora ponta"] == pytest.approx(1250.4523, abs=0.01)
    assert r.componentes["Demanda ponta"] == pytest.approx(sum(ponta) * 28.41)


def test_limite_de_ultrapassagem_segue_a_contratada_e_nao_63_fixo():
    # Com 100 kW contratados, 104 kW está dentro da tolerância e 106 kW não.
    e = _entrada(demanda_fp_kw=[104.0] * 6 + [106.0] * 6, demanda_contratada_kw=100.0,
                 verde=TarifasVerde(demanda=10.0, consumo_ponta=1.0, consumo_fp=0.5))
    r = SimuladorTarifas(e).verde()
    assert r.meses_com_ultrapassagem == 6
    assert r.ultrapassagem_anual == pytest.approx(6 * 6 * 10.0 * 2)


def test_contratada_igual_a_medida_sobre_tolerancia_nao_gera_ultrapassagem():
    e = _entrada(demanda_fp_kw=[105.0] * 12, demanda_contratada_kw=105.0 / 1.05,
                 verde=TarifasVerde(demanda=10.0, consumo_ponta=1.0, consumo_fp=0.5))
    assert SimuladorTarifas(e).verde().ultrapassagem_anual == 0.0


def test_tarifa_umida_aplica_de_dezembro_a_abril():
    e = _entrada(consumo_ponta_kwh=[100.0] * 12,
                 verde=TarifasVerde(demanda=0.0, consumo_ponta=1.0, consumo_fp=0.0, consumo_ponta_umido=2.0))
    r = SimuladorTarifas(e).verde()
    # úmido: jan–abr + dez (5 meses a 2,0); seco: mai–nov (7 meses a 1,0)
    assert r.componentes["Consumo ponta"] == pytest.approx(5 * 200 + 7 * 100)
    assert r.custo_mensal[0] == pytest.approx(200) and r.custo_mensal[5] == pytest.approx(100)


def test_demanda_unica_usa_a_maior_entre_ponta_e_fora_ponta():
    e = _entrada(demanda_ponta_kw=[80.0] * 12, demanda_fp_kw=[50.0] * 12, demanda_contratada_kw=80.0,
                 convencional=TarifasConvencional(demanda=10.0, consumo=0.0))
    assert SimuladorTarifas(e).convencional().componentes["Demanda"] == pytest.approx(12 * 800)


def test_recomenda_a_mais_barata_e_ignora_modalidade_sem_tarifa():
    e = _entrada(consumo_fp_kwh=[1000.0] * 12,
                 convencional=TarifasConvencional(demanda=0.0, consumo=0.5),
                 baixa_tensao=TarifasBaixaTensao(consumo=0.4))
    r = SimuladorTarifas(e).simular()
    assert [m.modalidade for m in r.modalidades] == ["Convencional", "Baixa Tensão"]
    assert r.recomendada == "Baixa Tensão"
    assert r.economia_vs_atual["Convencional"] == pytest.approx(1200.0)


def test_demanda_sugerida_minimiza_o_custo():
    medidas = [60.0] * 11 + [90.0]
    e = _entrada(demanda_fp_kw=medidas, demanda_contratada_kw=90.0,
                 verde=TarifasVerde(demanda=10.0, consumo_ponta=0.0, consumo_fp=0.0))
    sim = SimuladorTarifas(e)
    r = sim.simular()
    sug = r.demandas_sugeridas[0]
    # Força bruta em passos de 0,01 kW: nenhuma contratada é mais barata.
    melhor = min(sim._custo_demanda_anual(medidas, c / 100, 10.0) for c in range(0, 10001))
    assert sug.custo_anual == pytest.approx(melhor, abs=1e-6)
    assert sug.demanda_kw == pytest.approx(60.0)  # pagar 1 ultrapassagem sai mais barato que 90 o ano todo
    assert sug.economia_anual == pytest.approx(90 * 12 * 10 - melhor)


def test_validacao_rejeita_meses_faltando_e_sem_tarifas():
    e = InputSimuladorTarifas(demanda_ponta_kw=[1.0] * 11)
    erros = e.validar()
    assert "demanda_ponta_kw deve ter 12 meses (recebido: 11)." in erros
    assert "Informe as tarifas de pelo menos uma modalidade." in erros
    with pytest.raises(ValueError):
        SimuladorTarifas(e).simular()


def test_exemplo_simula_as_tres_modalidades_do_grupo_a():
    r = SimuladorTarifas(exemplo_simulador_tarifas()).simular()
    assert [m.modalidade for m in r.modalidades] == ["Convencional", "Azul", "Verde"]
    assert r.recomendada == "Convencional"
    assert all(len(m.custo_mensal) == 12 for m in r.modalidades)
    for m in r.modalidades:
        assert m.custo_anual == pytest.approx(sum(m.componentes.values()))


def test_tarifa_de_demanda_zero_mantem_a_contratada_atual():
    e = _entrada(demanda_fp_kw=[80.0] * 12, demanda_contratada_kw=75.0,
                 convencional=TarifasConvencional(demanda=0.0, consumo=0.5))
    sug = SimuladorTarifas(e).simular().demandas_sugeridas[0]
    assert sug.demanda_kw == 75.0
    assert sug.economia_anual == 0.0
