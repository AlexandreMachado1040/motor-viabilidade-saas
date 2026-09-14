"""Regras de negócio da administração de usuários e licenças."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import MODULOS, ModuleLicense, User
from .schemas import AdminUser


def _para_admin_user(user: User) -> AdminUser:
    ativos = user.modulos_ativos
    return AdminUser(
        id=user.id,
        email=user.email,
        name=user.name,
        provider=user.provider,
        is_active=user.is_active,
        is_admin=user.is_admin,
        modulos={m: (m in ativos) for m in MODULOS},
    )


def listar_usuarios(db: Session) -> list[AdminUser]:
    usuarios = db.scalars(select(User).order_by(User.id)).all()
    return [_para_admin_user(u) for u in usuarios]


def obter_usuario(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return user


def definir_modulos(db: Session, user_id: int, modulos: dict[str, bool]) -> AdminUser:
    desconhecidos = set(modulos) - set(MODULOS)
    if desconhecidos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Módulos inválidos: {sorted(desconhecidos)}",
        )
    user = obter_usuario(db, user_id)
    existentes = {lic.module: lic for lic in user.licenses}
    for modulo, habilitado in modulos.items():
        lic = existentes.get(modulo)
        if lic is None:
            db.add(ModuleLicense(user_id=user.id, module=modulo, enabled=habilitado, source="manual"))
        else:
            # Ação manual do admin sobrescreve a origem — mesmo que a licença
            # tivesse vindo de prova aprovada (source='exam'), a partir daqui
            # é o admin que está decidindo (achado de segurança/auditoria,
            # revisão Codex: source ficava mentindo depois de um toggle manual).
            lic.enabled = habilitado
            lic.source = "manual"
            lic.granted_at = func.now()
    db.commit()
    db.refresh(user)
    return _para_admin_user(user)


def definir_admin(db: Session, user_id: int, valor: bool) -> AdminUser:
    user = obter_usuario(db, user_id)
    user.is_admin = valor
    db.commit()
    db.refresh(user)
    return _para_admin_user(user)


def definir_ativo(db: Session, user_id: int, valor: bool) -> AdminUser:
    user = obter_usuario(db, user_id)
    user.is_active = valor
    db.commit()
    db.refresh(user)
    return _para_admin_user(user)
