"""Validação e cálculo de derivados do MOD 1 — InputLoad."""
from __future__ import annotations

from ...integracao.motor import get_input_load_cls
from .schemas import InputLoadPayload, LoadResumo


def _validar_estrutura(p: InputLoadPayload) -> list[str]:
    erros: list[str] = []
    if len(p.demanda_kw) != 12:
        erros.append(f"demanda_kw deve ter 12 meses (recebido: {len(p.demanda_kw)}).")
    for i, linha in enumerate(p.demanda_kw):
        if len(linha) != 24:
            erros.append(f"demanda_kw[{i}] deve ter 24 horas (recebido: {len(linha)}).")
    if len(p.energia_ponta_kwh) != 12:
        erros.append(
            f"energia_ponta_kwh deve ter 12 meses (recebido: {len(p.energia_ponta_kwh)})."
        )
    if len(p.energia_fp_kwh) != 12:
        erros.append(
            f"energia_fp_kwh deve ter 12 meses (recebido: {len(p.energia_fp_kwh)})."
        )
    return erros


def validar_load(p: InputLoadPayload) -> LoadResumo:
    erros = _validar_estrutura(p)
    if erros:
        return LoadResumo(valido=False, erros=erros)

    pico_mensal = [max(linha) if linha else 0.0 for linha in p.demanda_kw]
    demanda_maxima = p.demanda_maxima_kw or (max(pico_mensal) if pico_mensal else 0.0)

    # Usa o InputLoad do motor quando disponível (fonte de verdade dos derivados).
    InputLoad = get_input_load_cls()
    if InputLoad is not None:
        load = InputLoad(
            demanda_maxima_kw=demanda_maxima,
            demanda_kw=p.demanda_kw,
            energia_ponta_kwh=p.energia_ponta_kwh,
            energia_fp_kwh=p.energia_fp_kwh,
        )
        load.validar()  # redundante, mas garante consistência com o motor
        equivalente = load.energia_equivalente_kwh
        ponta_total = load.energia_ponta_total
        fp_total = load.energia_fp_total
    else:
        equivalente = [pt + fp for pt, fp in zip(p.energia_ponta_kwh, p.energia_fp_kwh)]
        ponta_total = sum(p.energia_ponta_kwh)
        fp_total = sum(p.energia_fp_kwh)

    return LoadResumo(
        valido=True,
        erros=[],
        demanda_maxima_kw=demanda_maxima,
        energia_ponta_total=ponta_total,
        energia_fp_total=fp_total,
        energia_total=ponta_total + fp_total,
        energia_equivalente_kwh=equivalente,
        pico_mensal_kw=pico_mensal,
    )
