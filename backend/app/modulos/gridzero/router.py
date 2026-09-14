"""Rotas do MOD 11 — InputGridZero. Navegação PRIVADA: exige licença do módulo 'gridzero'.

Sem rota /exemplo — `exemplo_planilha_original()` não carrega gridzero (tem
sua própria fonte de exemplo no motor, `exemplo_gridzero_planilha()`, mas
essa devolve uma comparação de 5 tamanhos de sistema, não um único
InputGridZero pra pré-preencher formulário — formato incompatível com o
padrão de /exemplo dos outros módulos)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import require_module
from .schemas import GridZeroResumo, InputGridZeroPayload
from .service import validar_gridzero

router = APIRouter(
    prefix="/modulos/gridzero",
    tags=["modulo:gridzero"],
    dependencies=[Depends(require_module("gridzero"))],
)


@router.post("/validar", response_model=GridZeroResumo)
def validar(payload: InputGridZeroPayload) -> GridZeroResumo:
    """Valida o sistema GridZero e roda o cálculo completo (energético + financeiro)."""
    resumo = validar_gridzero(payload)
    if resumo is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Cálculo indisponível (pacote motor_viabilidade não encontrado).",
        )
    return resumo
