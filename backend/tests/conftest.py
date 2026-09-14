"""Fixtures compartilhadas: banco em memória por teste + client autenticado.

Este é o primeiro conftest do backend (não havia nenhum teste automatizado
antes desta feature) — decisões aqui valem de referência pra próximos testes.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base, get_db
from app.db.models import User
from app.main import app


@pytest.fixture()
def db_engine():
    # StaticPool: uma única conexão sqlite:///:memory: compartilhada — sem
    # isso, cada `get_db()` (ou cada thread, em teste de concorrência) abriria
    # um banco em memória DIFERENTE e vazio. `check_same_thread=False` porque
    # os testes de corrida abrem sessão a partir de outra thread.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session(db_engine) -> Iterator[Session]:
    TestingSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _criar_usuario(db: Session, *, email: str, is_admin: bool = False) -> User:
    user = User(
        email=email, name=email.split("@")[0], provider="google",
        provider_sub=f"sub-{email}", is_active=True, is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def usuario(db_session: Session) -> User:
    return _criar_usuario(db_session, email="candidato@example.com")


@pytest.fixture()
def outro_usuario(db_session: Session) -> User:
    return _criar_usuario(db_session, email="outro@example.com")


@pytest.fixture()
def admin_usuario(db_session: Session) -> User:
    return _criar_usuario(db_session, email="admin@example.com", is_admin=True)


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}
