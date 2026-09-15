"""Simulação de modalidades tarifárias (MOD 2) — delega ao motor Python."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import HTTPException, status

from ...integracao.motor import get_simulador_tarifas_mod
from .tarifas_schemas import SimuladorTarifasPayload, SimuladorTarifasResumo


def _modulo():
    mod = get_simulador_tarifas_mod()
    if mod is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Simulador indisponível (pacote motor_viabilidade não encontrado).",
        )
    return mod


def montar_entrada(mod, p: SimuladorTarifasPayload):
    """Payload HTTP → motor_viabilidade.SimuladorTarifas.InputSimuladorTarifas."""
    dados = p.model_dump()
    classes = {
        "convencional": mod.TarifasConvencional,
        "azul": mod.TarifasAzul,
        "verde": mod.TarifasVerde,
        "baixa_tensao": mod.TarifasBaixaTensao,
    }
    for campo, cls in classes.items():
        if dados[campo] is not None:
            dados[campo] = cls(**dados[campo])
    return mod.InputSimuladorTarifas(**dados)


def simular_tarifas(p: SimuladorTarifasPayload) -> SimuladorTarifasResumo:
    mod = _modulo()
    entrada = montar_entrada(mod, p)

    erros = entrada.validar()
    if erros:
        return SimuladorTarifasResumo(valido=False, erros=erros)
    return SimuladorTarifasResumo(valido=True, **asdict(mod.SimuladorTarifas(entrada).simular()))


def exemplo_tarifas() -> SimuladorTarifasPayload:
    return SimuladorTarifasPayload(**asdict(_modulo().exemplo_simulador_tarifas()))


__all__ = ["montar_entrada", "simular_tarifas", "exemplo_tarifas"]
