"""Rotas do MOD 9 — ParamsCF. Navegação PRIVADA: exige licença do módulo 'cf'."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import require_module
from ...db.models import User
from ...integracao.motor import exemplo_params_cf_payload
from .schemas import ParamsCFPayload, ParamsCFResumo
from .service import validar_params_cf

router = APIRouter(
    prefix="/modulos/cf",
    tags=["modulo:cf"],
    dependencies=[Depends(require_module("cf"))],
)


@router.post("/validar", response_model=ParamsCFResumo)
def validar(payload: ParamsCFPayload) -> ParamsCFResumo:
    """Valida os parâmetros econômico-financeiros e devolve a taxa de desconto real."""
    return validar_params_cf(payload)


@router.get("/exemplo", response_model=ParamsCFPayload)
def exemplo(_user: User = Depends(require_module("cf"))) -> ParamsCFPayload:
    """Dados da planilha original para pré-preencher o formulário."""
    dados = exemplo_params_cf_payload()
    if dados is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Exemplo indisponível (pacote motor_viabilidade não encontrado).",
        )
    return ParamsCFPayload(**dados)
