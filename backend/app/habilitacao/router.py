"""Rotas de habilitação por prova.

Candidato: exige só login (get_current_user) — a prova é o caminho pra
CONSEGUIR a licença, não pode exigir a licença que ela concede.
Admin (autoria de provas): exige require_admin, mesmo guard de admin/router.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# Nota: usamos get_current_user, não require_module — a prova é o caminho
# pra CONSEGUIR a licença, não pode exigir a licença que ela concede.
from ..auth.dependencies import get_current_user, require_admin
from ..db.base import get_db
from ..db.models import User
from . import service
from .schemas import (
    ExamAdminView, ExamAttemptHistorico, ExamAttemptResultado, ExamAttemptStarted,
    ExamCreate, ExamPublic, SetExamAtivoRequest, SubmeterTentativaRequest,
)

router = APIRouter(prefix="/habilitacao", tags=["habilitacao"])


@router.get("/provas", response_model=list[ExamPublic])
def listar_provas(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ExamPublic]:
    return service.listar_provas_disponiveis(db, user)


@router.post("/provas/{exam_id}/iniciar", response_model=ExamAttemptStarted)
def iniciar_prova(
    exam_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ExamAttemptStarted:
    return service.iniciar_tentativa(db, user, exam_id)


@router.post("/tentativas/{attempt_id}/submeter", response_model=ExamAttemptResultado)
def submeter_prova(
    attempt_id: int,
    body: SubmeterTentativaRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamAttemptResultado:
    return service.submeter_tentativa(db, user, attempt_id, body.respostas)


@router.get("/tentativas/me", response_model=list[ExamAttemptHistorico])
def minhas_tentativas(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ExamAttemptHistorico]:
    return service.historico_tentativas(db, user)


# ── Admin: autoria de provas ─────────────────────────────────────────────────

admin_router = APIRouter(
    prefix="/habilitacao/admin", tags=["habilitacao:admin"],
    dependencies=[Depends(require_admin)],
)


@admin_router.get("/provas", response_model=list[ExamAdminView])
def admin_listar_provas(db: Session = Depends(get_db)) -> list[ExamAdminView]:
    return service.listar_provas_admin(db)


@admin_router.post("/provas", response_model=ExamAdminView, status_code=201)
def admin_criar_prova(payload: ExamCreate, db: Session = Depends(get_db)) -> ExamAdminView:
    return service.criar_prova(db, payload)


@admin_router.patch("/provas/{exam_id}/ativo", response_model=ExamAdminView)
def admin_definir_ativo(
    exam_id: int, body: SetExamAtivoRequest, db: Session = Depends(get_db)
) -> ExamAdminView:
    return service.definir_prova_ativa(db, exam_id, body.is_active)
