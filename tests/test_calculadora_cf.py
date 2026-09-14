"""Testes de `CalculadoraCF` — primeiro teste automatizado deste motor.

Existe por causa de um achado de auditoria (13/09): `cf_solar_scdee`,
`cf_bess_ponta` e `cf_gen_ponta` colocavam a economia operacional do
primeiro ano JUNTO com o CAPEX no "ano 0" — que `_descontar()` trata como
"agora", sem desconto algum. Resultado: o primeiro ano inteiro de economia
entrava duas vezes (uma sem desconto no ano 0, outra corretamente descontada
no ano 1), superestimando VPL/TIR e subestimando payback em todo relatório
de viabilidade que envolvesse esses três módulos.

Confirmado comparando contra `@aurova/financeiro` do app03
(`packages/core/financeiro`, TypeScript) com um cenário equivalente: antes
da correção, VPL/TIR/Payback divergiam (R$40.000 de diferença de VPL — um
ano de economia sem desconto, valor exato); depois, batem exatamente. Ver
dominios/financeiro-viabilidade-economica/spec.md."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from motor_viabilidade.CalculadoraCF import CalculadoraCF
from motor_viabilidade.ParamsCF import ParamsCF

# Cenário de referência: mesmo usado para comparar contra
# app03/packages/core/financeiro (TypeScript) — CAPEX 100k, economia plana de
# 40k/ano, 10 anos, desconto 10%, sem inflação/reajuste. Valores capturados
# de lá (calcularAnaliseFinanceira) são o "golden master" aqui.
PARAMS_REFERENCIA = ParamsCF(taxa_desconto=0.10, inflacao=0.0, anos_projeto=10, reajuste_tarifa_fp=0.0)


def test_ano_0_tem_so_capex_sem_nenhuma_linha_operacional():
    """O achado em si: ano 0 não pode ter economia, O&M ou opex — só CAPEX
    (e REPLACEMENT, que é pontual em anos específicos, não no ano 0)."""
    calc = CalculadoraCF(PARAMS_REFERENCIA)
    for cf in (
        calc.cf_solar_scdee(capex=100_000, om=1_000, saving_fp_energia=40_000,
                             custo_troca_inv=0, ano_troca=0),
        calc.cf_bess_ponta(capex=100_000, custo_reposicao=0, ano_reposicao=0,
                            opex_fp_carga=5_000, saving_ponta=40_000),
        calc.cf_gen_ponta(capex=100_000, om=1_000, vida_util=100, saving_ponta=40_000),
    ):
        assert cf["CAPITAL"][0] == -100_000
        for linha in ("O&M", "OPERATING_FP_ENERGIA", "OPERATING_P_ENERGIA", "OPERATING_FP_DEMANDA"):
            assert cf[linha][0] == 0.0, f"{linha}[0] deveria ser 0.0 (só CAPEX no ano 0), veio {cf[linha][0]}"


def test_cf_solar_scdee_bate_com_app03_calcularAnaliseFinanceira():
    """Cenário de referência (ver docstring do módulo) — capturado rodando
    app03/packages/core/financeiro/dist/index.js#calcularAnaliseFinanceira
    com os mesmos parâmetros (capex=100000, geração×tarifa=40000/ano,
    opex=0%, inflação=0%, desconto=10%, 10 anos)."""
    calc = CalculadoraCF(PARAMS_REFERENCIA)
    cf = calc.cf_solar_scdee(capex=100_000, om=0, saving_fp_energia=40_000,
                              custo_troca_inv=0, ano_troca=0)
    total = calc.totalizar_cf([cf])

    assert total == [-100_000.0] + [40_000.0] * 10

    vpl = calc.calcular_vpl(total)
    tir = calc.calcular_tir(total)
    payback = calc.calcular_payback(total)

    assert vpl == pytest.approx(145_782.68, abs=0.01)
    assert tir == pytest.approx(0.3845, abs=1e-4)
    assert payback == 3


def test_bug_do_ano_0_nao_volta__vpl_nao_pode_incluir_ano_extra_sem_desconto():
    """Regressão direta: reproduz o cálculo ERRADO (ano 0 com economia) só
    pra provar a diferença exata, e garante que a versão corrigida não bate
    com esse valor errado."""
    calc = CalculadoraCF(PARAMS_REFERENCIA)
    cf_correto = calc.cf_solar_scdee(capex=100_000, om=0, saving_fp_energia=40_000,
                                       custo_troca_inv=0, ano_troca=0)
    total_correto = calc.totalizar_cf([cf_correto])
    vpl_correto = calc.calcular_vpl(total_correto)

    # Reconstrução manual do comportamento ANTIGO (ano 0 com economia também).
    total_errado = list(total_correto)
    total_errado[0] += 40_000.0  # o "bônus" indevido que existia antes da correção
    vpl_errado = calc.calcular_vpl(total_errado)

    assert vpl_errado - vpl_correto == pytest.approx(40_000.0, abs=0.01), (
        "a diferença entre a versão com bug e a corrigida tem que ser exatamente "
        "um ano de economia sem desconto (o ano 0 não é descontado)"
    )
    assert vpl_correto == pytest.approx(145_782.68, abs=0.01)


def test_cf_bess_ponta_e_cf_gen_ponta_tambem_nao_duplicam_ano_0():
    calc = CalculadoraCF(PARAMS_REFERENCIA)

    cf_bess = calc.cf_bess_ponta(capex=100_000, custo_reposicao=0, ano_reposicao=0,
                                   opex_fp_carga=0, saving_ponta=40_000)
    total_bess = calc.totalizar_cf([cf_bess])
    assert total_bess == [-100_000.0] + [40_000.0] * 10
    assert calc.calcular_vpl(total_bess) == pytest.approx(145_782.68, abs=0.01)

    cf_gen = calc.cf_gen_ponta(capex=100_000, om=0, vida_util=100, saving_ponta=40_000)
    total_gen = calc.totalizar_cf([cf_gen])
    assert total_gen == [-100_000.0] + [40_000.0] * 10
    assert calc.calcular_vpl(total_gen) == pytest.approx(145_782.68, abs=0.01)


def test_new_grid_reaproveita_cf_grid_por_referencia_e_tambem_fica_correto():
    """`estudo_viabilidade.py` monta o cf do módulo `new_grid` reaproveitando
    as linhas OPERATING_* de `cf_grid` (mesmo objeto lista, não uma cópia) —
    ou seja, a correção de `cf_grid` afeta diretamente o VPL final desse
    cenário, não é só um ajuste cosmético de campo de exibição (achado da
    revisão Codex: minha primeira versão desta correção/spec dizia que
    corrigir `cf_grid` "não muda o resultado final" — impreciso para este
    caso específico, corrigido aqui com teste)."""
    calc = CalculadoraCF(PARAMS_REFERENCIA)
    cf_g = calc.cf_grid(opex_fp_energia=40_000, opex_p_energia=0, opex_fp_demanda=0)

    cf_ng = {
        "CAPITAL": [-50_000] + [0.0] * PARAMS_REFERENCIA.anos_projeto,
        "REPLACEMENT": [0.0] * (PARAMS_REFERENCIA.anos_projeto + 1),
        "O&M": [0.0] * (PARAMS_REFERENCIA.anos_projeto + 1),
        "OPERATING_FP_ENERGIA": cf_g["OPERATING_FP_ENERGIA"],
        "OPERATING_P_ENERGIA": cf_g["OPERATING_P_ENERGIA"],
        "OPERATING_FP_DEMANDA": cf_g["OPERATING_FP_DEMANDA"],
    }
    proposta = calc.totalizar_cf([cf_ng])
    assert proposta[0] == -50_000.0, (
        "ano 0 do cenário new_grid deveria ter só o CAPEX do new_grid, sem "
        "o custo operacional de grid duplicado junto (mesmo bug do ano 0, "
        "só que herdado de cf_grid por reaproveitamento de referência)"
    )


def test_cf_grid_baseline_tambem_zero_no_ano_0():
    """A série do grid (baseline/counterfactual) precisa da mesma convenção
    — senão `saving_serie`/`fc_total_nominal` (estudo_viabilidade.calcular_cf)
    ficam inconsistentes com os módulos de investimento."""
    calc = CalculadoraCF(PARAMS_REFERENCIA)
    cf = calc.cf_grid(opex_fp_energia=10_000, opex_p_energia=5_000, opex_fp_demanda=2_000)
    for linha in ("OPERATING_FP_ENERGIA", "OPERATING_P_ENERGIA", "OPERATING_FP_DEMANDA"):
        assert cf[linha][0] == 0.0
        assert len(cf[linha]) == PARAMS_REFERENCIA.anos_projeto + 1
