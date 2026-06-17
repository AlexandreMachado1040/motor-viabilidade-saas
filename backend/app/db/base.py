"""Engine, sessão e Base do SQLAlchemy."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from ..core.config import settings

_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db() -> Iterator[Session]:
    """Dependency do FastAPI: abre uma sessão por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
