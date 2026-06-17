"""Emissão e validação do JWT próprio (access + refresh)."""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

import jwt

from .config import settings

ALGS = [settings.jwt_algorithm]


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: dt.timedelta,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    return _create_token(
        subject, "access",
        dt.timedelta(minutes=settings.access_token_expire_minutes),
        extra,
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, "refresh",
        dt.timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: Optional[str] = None) -> dict[str, Any]:
    """Decodifica e valida assinatura/expiração. Levanta jwt.PyJWTError se inválido."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=ALGS)
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"Tipo de token inesperado: {payload.get('type')} != {expected_type}"
        )
    return payload
