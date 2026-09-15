"""Rotas do MOD 2 — InputGrid. Navegação PRIVADA: exige licença do módulo 'grid'."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import require_module
from ...db.models import User
from ...integracao.motor import exemplo_grid_payload
from .schemas import GridResumo, InputGridPayload
from .service import validar_grid
from .tarifas_schemas import SimuladorTarifasPayload, SimuladorTarifasResumo
from .tarifas_service import exemplo_tarifas, simular_tarifas

router = APIRouter(
    prefix="/modulos/grid",
    tags=["modulo:grid"],
    dependencies=[Depends(require_module("grid"))],
)


@router.post("/validar", response_model=GridResumo)
def validar(payload: InputGridPayload) -> GridResumo:
    """Valida as tarifas/encargos e devolve os derivados (tarifa ponta/fora-ponta)."""
    return validar_grid(payload)


@router.get("/exemplo", response_model=InputGridPayload)
def exemplo(_user: User = Depends(require_module("grid"))) -> InputGridPayload:
    """Dados da planilha original para pré-preencher o formulário."""
    dados = exemplo_grid_payload()
    if dados is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Exemplo indisponível (pacote motor_viabilidade não encontrado).",
        )
    return InputGridPayload(**dados)


@router.post("/simular-tarifas", response_model=SimuladorTarifasResumo)
def simular(payload: SimuladorTarifasPayload) -> SimuladorTarifasResumo:
    """Compara o custo anual das modalidades tarifárias e recomenda a mais barata."""
    return simular_tarifas(payload)


@router.get("/exemplo-tarifas", response_model=SimuladorTarifasPayload)
def exemplo_simulador() -> SimuladorTarifasPayload:
    """Dados da planilha SIMULADOR TARIFAS ANUAL para pré-preencher a página."""
    return exemplo_tarifas()
