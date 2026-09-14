"""Rotas do MOD 7 — InputBESSFormador. PRIVADA: exige licença do módulo 'bess_form'.

Sem rota /exemplo — `exemplo_planilha_original()` não carrega bess_form (ver
nota equivalente em modulos/new_grid/router.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auth.dependencies import require_module
from .schemas import BESSFormadorResumo, InputBESSFormadorPayload
from .service import validar_bess_formador

router = APIRouter(
    prefix="/modulos/bess_form",
    tags=["modulo:bess_form"],
    dependencies=[Depends(require_module("bess_form"))],
)


@router.post("/validar", response_model=BESSFormadorResumo)
def validar(payload: InputBESSFormadorPayload) -> BESSFormadorResumo:
    """Valida a bateria formadora de rede (off-grid/híbrido)."""
    return validar_bess_formador(payload)
