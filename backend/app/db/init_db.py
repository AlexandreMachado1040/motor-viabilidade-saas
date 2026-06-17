"""Criação das tabelas (skeleton — em produção use migrações Alembic)."""
from __future__ import annotations

from .base import Base, engine
from . import models  # noqa: F401  (garante o registro dos modelos no metadata)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
