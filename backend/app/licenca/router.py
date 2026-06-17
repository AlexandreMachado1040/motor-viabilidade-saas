"""Rotas de licença de módulo + exemplo de endpoint protegido por módulo."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_user, require_module
from ..db.models import User
from .service import flags_licenca

router = APIRouter(prefix="/licenca", tags=["licenca"])


@router.get("/me")
def minha_licenca(user: User = Depends(get_current_user)) -> dict[str, bool]:
    """Flags de módulos contratados pelo usuário (formato LicencaModulos)."""
    return flags_licenca(user)


@router.get("/exemplo/gridzero")
def exemplo_protegido(user: User = Depends(require_module("gridzero"))) -> dict[str, str]:
    """
    Endpoint de exemplo: só acessível por quem tem a licença do módulo 'gridzero'.
    Substitua pela chamada real ao motor_viabilidade.EstudoViabilidade.
    """
    return {"detail": f"Acesso liberado ao módulo GridZero para {user.email}."}
