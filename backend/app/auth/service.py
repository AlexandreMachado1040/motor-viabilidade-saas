"""Regras de negócio de autenticação: upsert de usuário e provisionamento de licenças."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.models import MODULOS, MODULOS_PADRAO, ModuleLicense, User


def _extrair_userinfo(provider: str, token: dict[str, Any], userinfo: dict[str, Any]) -> dict:
    """Normaliza o userinfo OIDC dos diferentes provedores."""
    sub = userinfo.get("sub") or userinfo.get("oid") or ""
    email = userinfo.get("email") or userinfo.get("preferred_username") or ""
    name = userinfo.get("name")
    picture = userinfo.get("picture")
    return {
        "provider_sub": str(sub),
        "email": email.lower().strip(),
        "name": name,
        "picture": picture,
    }


def upsert_usuario(
    db: Session, provider: str, token: dict[str, Any], userinfo: dict[str, Any]
) -> User:
    """Cria ou atualiza o usuário a partir do login social. Provisiona licenças padrão."""
    info = _extrair_userinfo(provider, token, userinfo)
    if not info["email"]:
        raise ValueError("Provedor não retornou e-mail; não é possível autenticar.")

    eh_admin = info["email"] in settings.admin_emails_set
    user = db.scalar(select(User).where(User.email == info["email"]))
    if user is None:
        user = User(
            email=info["email"],
            name=info["name"],
            picture=info["picture"],
            provider=provider,
            provider_sub=info["provider_sub"],
            is_admin=eh_admin,
        )
        db.add(user)
        db.flush()  # garante user.id
        # Admins recebem todos os módulos; demais, apenas os básicos.
        modulos_iniciais = MODULOS if eh_admin else MODULOS_PADRAO
        for modulo in modulos_iniciais:
            db.add(ModuleLicense(user_id=user.id, module=modulo, enabled=True))
    else:
        user.name = info["name"] or user.name
        user.picture = info["picture"] or user.picture
        user.provider = provider
        user.provider_sub = info["provider_sub"] or user.provider_sub
        # Promove a admin se o e-mail constar em ADMIN_EMAILS (não rebaixa aqui).
        if eh_admin and not user.is_admin:
            user.is_admin = True
            _garantir_modulos(db, user, MODULOS, enabled=True)

    db.commit()
    db.refresh(user)
    return user


def _garantir_modulos(db: Session, user: User, modulos, enabled: bool) -> None:
    """Garante a existência de linhas ModuleLicense para os módulos informados."""
    existentes = {lic.module: lic for lic in user.licenses}
    for modulo in modulos:
        lic = existentes.get(modulo)
        if lic is None:
            db.add(ModuleLicense(user_id=user.id, module=modulo, enabled=enabled))
        else:
            lic.enabled = enabled


def buscar_usuario(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)
