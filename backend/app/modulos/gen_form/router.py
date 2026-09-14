"""Rotas do MOD 6 — InputGeradorFormador. PRIVADA: exige licença do módulo 'gen_form'.

Sem rota /exemplo — `exemplo_planilha_original()` não carrega gen_form (ver
nota equivalente em modulos/new_grid/router.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auth.dependencies import require_module
from .schemas import GeradorFormadorResumo, InputGeradorFormadorPayload
from .service import validar_gerador_formador

router = APIRouter(
    prefix="/modulos/gen_form",
    tags=["modulo:gen_form"],
    dependencies=[Depends(require_module("gen_form"))],
)


@router.post("/validar", response_model=GeradorFormadorResumo)
def validar(payload: InputGeradorFormadorPayload) -> GeradorFormadorResumo:
    """Valida o gerador diesel formador de rede."""
    return validar_gerador_formador(payload)
