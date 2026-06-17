"""Modelos ORM: usuário e licenças de módulo (espelham motor_viabilidade.LicencaModulos)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Módulos licenciáveis — mesmas chaves de motor_viabilidade.LicencaModulos.
# Por padrão liberamos os módulos básicos (espelha os defaults da dataclass).
MODULOS = [
    "load", "grid", "solar", "bess_ponta", "gen_ponta", "gen_form",
    "bess_form", "new_grid", "cf", "summary", "gridzero",
]
MODULOS_PADRAO = {"load", "grid", "cf", "summary"}


class User(Base):
    __tablename__ = "users"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True)
    email:        Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name:         Mapped[str | None] = mapped_column(String(255))
    picture:      Mapped[str | None] = mapped_column(String(1024))
    provider:     Mapped[str] = mapped_column(String(32))          # google | microsoft
    provider_sub: Mapped[str] = mapped_column(String(255), index=True)
    is_active:    Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin:     Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:   Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at:   Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    licenses: Mapped[list["ModuleLicense"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin")

    @property
    def modulos_ativos(self) -> set[str]:
        return {lic.module for lic in self.licenses if lic.enabled}


class ModuleLicense(Base):
    __tablename__ = "module_licenses"
    __table_args__ = (UniqueConstraint("user_id", "module", name="uq_user_module"),)

    id:      Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module:  Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="licenses")
