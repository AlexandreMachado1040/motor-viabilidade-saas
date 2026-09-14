"""Rotas do MOD 3 — InputSolarSCDEE. Navegação PRIVADA: exige licença do módulo 'solar'."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import require_module
from ...db.models import User
from ...integracao.motor import exemplo_solar_scdee_payload
from .schemas import InputSolarSCDEEPayload, SolarSCDEEResumo
from .service import validar_solar_scdee

router = APIRouter(
    prefix="/modulos/solar",
    tags=["modulo:solar"],
    dependencies=[Depends(require_module("solar"))],
)


@router.post("/validar", response_model=SolarSCDEEResumo)
def validar(payload: InputSolarSCDEEPayload) -> SolarSCDEEResumo:
    """Valida o sistema solar GD/compensação e devolve os derivados mensais."""
    return validar_solar_scdee(payload)


@router.get("/exemplo", response_model=InputSolarSCDEEPayload)
def exemplo(_user: User = Depends(require_module("solar"))) -> InputSolarSCDEEPayload:
    """Dados da planilha original para pré-preencher o formulário."""
    dados = exemplo_solar_scdee_payload()
    if dados is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Exemplo indisponível (pacote motor_viabilidade não encontrado).",
        )
    return InputSolarSCDEEPayload(**dados)
