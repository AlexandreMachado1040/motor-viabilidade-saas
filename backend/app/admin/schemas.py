"""Schemas da área administrativa."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class AdminUser(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None
    provider: str
    is_active: bool
    is_admin: bool
    modulos: dict[str, bool]


class SetModulosRequest(BaseModel):
    """Mapa parcial ou total {modulo: habilitado}."""
    modulos: dict[str, bool]


class SetAdminRequest(BaseModel):
    is_admin: bool


class SetAtivoRequest(BaseModel):
    is_active: bool
