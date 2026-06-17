"""Rotas administrativas — protegidas por require_admin."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth.dependencies import require_admin
from ..db.base import get_db
from ..db.models import MODULOS, User
from . import service
from .schemas import AdminUser, SetAdminRequest, SetAtivoRequest, SetModulosRequest

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/modulos")
def modulos_disponiveis() -> list[str]:
    """Lista canônica de módulos licenciáveis."""
    return MODULOS


@router.get("/users", response_model=list[AdminUser])
def listar_usuarios(db: Session = Depends(get_db)) -> list[AdminUser]:
    return service.listar_usuarios(db)


@router.put("/users/{user_id}/modulos", response_model=AdminUser)
def definir_modulos(
    user_id: int, body: SetModulosRequest, db: Session = Depends(get_db)
) -> AdminUser:
    return service.definir_modulos(db, user_id, body.modulos)


@router.patch("/users/{user_id}/admin", response_model=AdminUser)
def definir_admin(
    user_id: int, body: SetAdminRequest, db: Session = Depends(get_db)
) -> AdminUser:
    return service.definir_admin(db, user_id, body.is_admin)


@router.patch("/users/{user_id}/ativo", response_model=AdminUser)
def definir_ativo(
    user_id: int, body: SetAtivoRequest, db: Session = Depends(get_db)
) -> AdminUser:
    return service.definir_ativo(db, user_id, body.is_active)
