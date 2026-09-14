"""Rotas do MOD 4 — InputBESSPonta. Navegação PRIVADA: exige licença do módulo 'bess_ponta'."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import require_module
from ...db.models import User
from ...integracao.motor import exemplo_bess_ponta_payload
from .schemas import BESSPontaResumo, InputBESSPontaPayload
from .service import validar_bess_ponta

router = APIRouter(
    prefix="/modulos/bess_ponta",
    tags=["modulo:bess_ponta"],
    dependencies=[Depends(require_module("bess_ponta"))],
)


@router.post("/validar", response_model=BESSPontaResumo)
def validar(payload: InputBESSPontaPayload) -> BESSPontaResumo:
    """Valida a bateria de ponta e devolve os derivados (energia útil no EoL)."""
    return validar_bess_ponta(payload)


@router.get("/exemplo", response_model=InputBESSPontaPayload)
def exemplo(_user: User = Depends(require_module("bess_ponta"))) -> InputBESSPontaPayload:
    """Dados da planilha original para pré-preencher o formulário."""
    dados = exemplo_bess_ponta_payload()
    if dados is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Exemplo indisponível (pacote motor_viabilidade não encontrado).",
        )
    return InputBESSPontaPayload(**dados)
