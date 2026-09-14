"""Dependências de autorização: usuário atual e exigência de módulo licenciado."""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.security import decode_token
from ..db.base import get_db
from ..db.models import User
from .service import buscar_usuario

bearer = HTTPBearer(auto_error=True)


def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(cred.credentials, expected_type="access")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise cred_exc

    user = buscar_usuario(db, user_id)
    if user is None or not user.is_active:
        raise cred_exc
    return user


def require_module(modulo: str):
    """Fábrica de dependency que exige a licença de um módulo específico —
    inclusive validade: `user.modulos_ativos` (única fonte de verdade, ver
    db/models.py) já exclui licença com `expires_at` vencido, então uma
    licença expirada é tratada exatamente como módulo nunca contratado no
    ponto de decisão. A única diferença aqui é a mensagem de erro: se existe
    uma `ModuleLicense` para o módulo mas ela caiu fora de `modulos_ativos`
    por expiração (não por `enabled=False`), avisamos que expirou em vez de
    dizer "não contratado" — mais preciso pro usuário que já teve acesso."""
    def _dep(user: User = Depends(get_current_user)) -> User:
        if modulo not in user.modulos_ativos:
            lic = next((l for l in user.licenses if l.module == modulo), None)
            if lic is not None and lic.enabled and lic.expirada():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Licença do módulo '{modulo}' expirou. Renove para continuar com acesso.",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(f"Módulo '{modulo}' não contratado. "
                        "Adquira a licença correspondente para acesso."),
            )
        return user
    return _dep


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Exige que o usuário autenticado seja administrador."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return user
