"""Rotas do MOD 10 — Summary. Navegação PRIVADA: exige licença do módulo 'summary'.

Sem rota /exemplo — não existe um "InputSummary" de exemplo (o resumo é
derivado de todos os outros módulos, cada um já com seu próprio /exemplo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import require_module
from .schemas import SummaryPayload, SummaryResumo
from .service import validar_summary

router = APIRouter(
    prefix="/modulos/summary",
    tags=["modulo:summary"],
    dependencies=[Depends(require_module("summary"))],
)


@router.post("/validar", response_model=SummaryResumo)
def validar(payload: SummaryPayload) -> SummaryResumo:
    """Roda o estudo de viabilidade completo (load+grid+módulos de investimento
    enviados) e devolve o resumo final: VPL, TIR, payback, ROI, viabilidade."""
    resumo = validar_summary(payload)
    if resumo is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Cálculo indisponível (pacote motor_viabilidade não encontrado).",
        )
    return resumo
