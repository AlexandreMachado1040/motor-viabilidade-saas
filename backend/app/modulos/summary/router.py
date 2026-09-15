"""Rotas do MOD 10 — Summary. Navegação PRIVADA: exige licença do módulo 'summary'.

Sem rota /exemplo — não existe um "InputSummary" de exemplo (o resumo é
derivado de todos os outros módulos, cada um já com seu próprio /exemplo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import require_module
from ...db.models import User
from .schemas import SummaryPayload, SummaryResumo
from .service import validar_summary

router = APIRouter(
    prefix="/modulos/summary",
    tags=["modulo:summary"],
    dependencies=[Depends(require_module("summary"))],
)


# Blocos opcionais do payload → licença que cada um exige. A licença de
# `summary` sozinha não dá direito a calcular módulos não contratados enviando
# o bloco à mão (o frontend já não envia, mas a regra vale no servidor).
LICENCA_POR_BLOCO = {
    "solar": "solar",
    "bess_ponta": "bess_ponta",
    "gen_ponta": "gen_ponta",
    "gen_form": "gen_form",
    "bess_form": "bess_form",
    "new_grid": "new_grid",
    "tarifas": "grid",
}


@router.post("/validar", response_model=SummaryResumo)
def validar(payload: SummaryPayload, user: User = Depends(require_module("summary"))) -> SummaryResumo:
    """Roda o estudo de viabilidade completo (load+grid+módulos de investimento
    enviados) e devolve o resumo final: VPL, TIR, payback, ROI, viabilidade."""
    sem_licenca = sorted({
        modulo for bloco, modulo in LICENCA_POR_BLOCO.items()
        if getattr(payload, bloco) is not None and modulo not in user.modulos_ativos
    })
    if sem_licenca:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Módulos não contratados no estudo: {', '.join(sem_licenca)}.",
        )
    resumo = validar_summary(payload)
    if resumo is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Cálculo indisponível (pacote motor_viabilidade não encontrado).",
        )
    return resumo
