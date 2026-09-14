"""Validação e cálculo de derivados do MOD 3 — InputSolarSCDEE."""
from __future__ import annotations

from ...integracao.motor import get_input_solar_scdee_cls
from .schemas import InputSolarSCDEEPayload, SolarSCDEEResumo


def validar_solar_scdee(p: InputSolarSCDEEPayload) -> SolarSCDEEResumo:
    # InputSolarSCDEE não tem `.validar()` — os próprios métodos derivados
    # toleram `potencia_gerada_kw`/`potencia_injetada_kw` vazios ou com menos
    # de 12 meses (devolvem 0.0 pro mês ausente), então não há estrutura
    # obrigatória pra rejeitar aqui além do que o Pydantic já garante.
    InputSolarSCDEE = get_input_solar_scdee_cls()
    if InputSolarSCDEE is not None:
        solar = InputSolarSCDEE(**p.model_dump())
        periodo = solar.periodo_transicao_vigente
        gerada = solar.energia_gerada_mensal_kwh()
        injetada = solar.energia_injetada_mensal_kwh()
    else:
        periodo = _periodo_transicao_vigente_fallback(p)
        gerada = [sum(p.potencia_gerada_kw[m]) if m < len(p.potencia_gerada_kw) else 0.0
                  for m in range(12)]
        injetada = [abs(sum(p.potencia_injetada_kw[m])) if m < len(p.potencia_injetada_kw) else 0.0
                    for m in range(12)]

    return SolarSCDEEResumo(
        valido=True, erros=[],
        periodo_transicao_vigente=periodo,
        energia_gerada_mensal_kwh=gerada,
        energia_injetada_mensal_kwh=injetada,
    )


def _periodo_transicao_vigente_fallback(p: InputSolarSCDEEPayload) -> float:
    for ano in sorted(p.cronograma_transicao.keys(), reverse=True):
        if p.data_estudo_ano >= ano:
            return p.cronograma_transicao[ano]
    return 0.0


__all__ = ["validar_solar_scdee"]
