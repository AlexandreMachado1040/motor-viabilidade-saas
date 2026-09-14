"""Rotas do MOD 8 — InputNewGrid. Navegação PRIVADA: exige licença do módulo 'new_grid'.

Sem rota /exemplo: `exemplo_planilha_original()` (a única fonte de exemplo do
motor) não carrega new_grid — não existe dado de referência pra pré-preencher
(diferente de load/grid/solar/bess_ponta/cf, que a planilha original cobre)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auth.dependencies import require_module
from .schemas import InputNewGridPayload, NewGridResumo
from .service import validar_new_grid

router = APIRouter(
    prefix="/modulos/new_grid",
    tags=["modulo:new_grid"],
    dependencies=[Depends(require_module("new_grid"))],
)


@router.post("/validar", response_model=NewGridResumo)
def validar(payload: InputNewGridPayload) -> NewGridResumo:
    """Valida o custo de implantação de nova rede."""
    return validar_new_grid(payload)
