"""Rotas do MOD 5 — InputGeradorPonta. PRIVADA: exige licença do módulo 'gen_ponta'.

Sem rota /exemplo — `exemplo_planilha_original()` não carrega gen_ponta (ver
nota equivalente em modulos/new_grid/router.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auth.dependencies import require_module
from .schemas import GeradorPontaResumo, InputGeradorPontaPayload
from .service import validar_gerador_ponta

router = APIRouter(
    prefix="/modulos/gen_ponta",
    tags=["modulo:gen_ponta"],
    dependencies=[Depends(require_module("gen_ponta"))],
)


@router.post("/validar", response_model=GeradorPontaResumo)
def validar(payload: InputGeradorPontaPayload) -> GeradorPontaResumo:
    """Valida o gerador diesel de ponta e devolve o custo de diesel por kWh."""
    return validar_gerador_ponta(payload)
