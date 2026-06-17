"""Rotas do MOD 1 — InputLoad. Navegação PRIVADA: exige licença do módulo 'load'."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import require_module
from ...db.models import User
from ...integracao.motor import exemplo_load_payload
from .schemas import InputLoadPayload, LoadResumo
from .service import validar_load

# Todas as rotas exigem o usuário autenticado COM a licença do módulo 'load'.
router = APIRouter(
    prefix="/modulos/load",
    tags=["modulo:load"],
    dependencies=[Depends(require_module("load"))],
)


@router.post("/validar", response_model=LoadResumo)
def validar(payload: InputLoadPayload) -> LoadResumo:
    """Valida a memória de massa e devolve os derivados (totais, equivalente, picos)."""
    return validar_load(payload)


@router.get("/exemplo", response_model=InputLoadPayload)
def exemplo(_user: User = Depends(require_module("load"))) -> InputLoadPayload:
    """Dados da planilha original para pré-preencher o formulário."""
    dados = exemplo_load_payload()
    if dados is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Exemplo indisponível (pacote motor_viabilidade não encontrado).",
        )
    return InputLoadPayload(**dados)
