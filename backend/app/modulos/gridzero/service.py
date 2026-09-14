"""Validação e cálculo do MOD 11 — InputGridZero.

Ao contrário dos MOD 3-9, não há fallback replicando a fórmula financeira
quando `motor_viabilidade` está indisponível — o cálculo (`calcular_financeiro`,
projeção de 25 anos com desconto/reajuste) é rico demais pra duplicar aqui
com segurança (mesmo risco que motivou não portar a TIR/VPL do
CalculadoraCF pro backend em nenhum outro lugar). Sem o motor, a rota
devolve 503 (ver router.py), igual já acontece pros endpoints /exemplo."""
from __future__ import annotations

from ...integracao.motor import get_calculadora_gridzero_cls, get_input_gridzero_cls
from .schemas import GridZeroResumo, InputGridZeroPayload


def _validar_estrutura(p: InputGridZeroPayload) -> list[str]:
    # Mesmas 4 checagens de InputGridZero.validar() no motor, mas coletando
    # todos os erros de uma vez em vez de parar no primeiro `assert` (mesmo
    # padrão de load._validar_estrutura) — e evita propagar um AssertionError
    # cru (500) se o payload vier estruturalmente inválido.
    erros: list[str] = []
    if len(p.demanda_horaria_kw) != 24:
        erros.append(f"demanda_horaria_kw deve ter 24 valores (recebido: {len(p.demanda_horaria_kw)}).")
    if len(p.perfil_solar_norm) != 24:
        erros.append(f"perfil_solar_norm deve ter 24 valores (recebido: {len(p.perfil_solar_norm)}).")
    if p.potencia_ac_kw <= 0:
        erros.append("potencia_ac_kw deve ser positivo.")
    if p.capex_kwp <= 0:
        erros.append("capex_kwp deve ser positivo.")
    return erros


def validar_gridzero(p: InputGridZeroPayload) -> GridZeroResumo | None:
    """Devolve `None` quando o motor está indisponível (router converte pra 503)."""
    erros = _validar_estrutura(p)
    if erros:
        return GridZeroResumo(valido=False, erros=erros)

    InputGridZero = get_input_gridzero_cls()
    CalculadoraGridZero = get_calculadora_gridzero_cls()
    if InputGridZero is None or CalculadoraGridZero is None:
        return None

    gz = InputGridZero(**p.model_dump())
    resultado = CalculadoraGridZero(gz).calcular()

    return GridZeroResumo(
        valido=True, erros=[],
        potencia_ac_kw=resultado.potencia_ac_kw,
        potencia_cc_kwp=resultado.potencia_cc_kwp,
        capex_total_r=resultado.capex_total_r,
        autoconsumo_kwh_dia=resultado.autoconsumo_kwh_dia,
        geracao_gz_kwh_dia=resultado.geracao_gz_kwh_dia,
        consumo_total_kwh_dia=resultado.consumo_total_kwh_dia,
        excedente_kwh_dia=resultado.excedente_kwh_dia,
        autoconsumo_pct=resultado.autoconsumo_pct,
        simultaneidade_pct=resultado.simultaneidade_pct,
        autoconsumo_anual_kwh=resultado.autoconsumo_anual_kwh,
        geracao_anual_kwh=resultado.geracao_anual_kwh,
        consumo_anual_kwh=resultado.consumo_anual_kwh,
        saving_ano1_r=resultado.saving_ano1_r,
        payback_anos=resultado.payback_anos,
        vpl_r=resultado.vpl_r,
        vpl_kwp_r=resultado.vpl_kwp_r,
        tma_pct=resultado.tma_pct,
        tarifa_kwh=resultado.tarifa_kwh,
        fc_nominal=resultado.fc_nominal,
        fc_acumulado=resultado.fc_acumulado,
    )


__all__ = ["validar_gridzero"]
