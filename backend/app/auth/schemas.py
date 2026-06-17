"""Schemas Pydantic da camada de autenticação."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str | None = None
    picture: str | None = None
    provider: str
    is_active: bool
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class MeResponse(BaseModel):
    usuario: UsuarioPublico
    modulos: dict[str, bool]


class DevLoginRequest(BaseModel):
    """Apenas para desenvolvimento local (DEV_LOGIN_ENABLED=true)."""
    email: EmailStr
    name: str | None = None
