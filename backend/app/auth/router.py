"""
Rotas de autenticação.

Fluxo (Authorization Code / OIDC, híbrido com JWT próprio):
  1. Front redireciona o navegador para  GET /auth/login/{provider}
  2. Backend redireciona ao provedor (Google/Microsoft)
  3. Provedor retorna em  GET /auth/callback/{provider}
  4. Backend troca o code, lê o userinfo, faz upsert do usuário,
     emite access_token (resposta) + refresh_token (cookie httpOnly) e
     redireciona o navegador de volta ao front.
  5. Front chama POST /auth/refresh (cookie) para obter o access_token.
"""
from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import (
    create_access_token, create_refresh_token, decode_token,
)
from ..db.base import get_db
from ..db.models import MODULOS
from .dependencies import get_current_user
from .oauth import oauth, provedor_disponivel
from .schemas import DevLoginRequest, MeResponse, TokenResponse, UsuarioPublico
from .service import buscar_usuario, upsert_usuario

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = settings.refresh_token_expire_days * 24 * 3600


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.backend_url.startswith("https"),
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/auth",
    )


def _validar_provedor(provider: str) -> None:
    if provider not in ("google", "microsoft"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Provedor '{provider}' inexistente.")
    if not provedor_disponivel(provider):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Provedor '{provider}' não configurado (defina CLIENT_ID/SECRET no .env).",
        )


@router.get("/providers")
def listar_provedores() -> dict[str, bool]:
    """Indica ao front quais botões de login exibir."""
    return {
        "google": settings.google_enabled,
        "microsoft": settings.microsoft_enabled,
        "dev": settings.dev_login_enabled,
    }


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(
    body: DevLoginRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Login de desenvolvimento (sem OAuth). Disponível apenas quando
    DEV_LOGIN_ENABLED=true. NÃO habilitar em produção.
    """
    if not settings.dev_login_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Não encontrado.")
    user = upsert_usuario(
        db, "dev", {},
        {"sub": body.email, "email": body.email, "name": body.name or body.email},
    )
    _set_refresh_cookie(response, create_refresh_token(str(user.id)))
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    _validar_provedor(provider)
    redirect_uri = f"{settings.backend_url}/auth/callback/{provider}"
    client = getattr(oauth, provider)
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def callback(provider: str, request: Request, db: Session = Depends(get_db)):
    _validar_provedor(provider)
    client = getattr(oauth, provider)
    try:
        token = await client.authorize_access_token(request)
    except Exception as exc:  # OAuthError, etc.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Falha no OAuth: {exc}")

    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await client.userinfo(token=token)

    try:
        user = upsert_usuario(db, provider, token, dict(userinfo))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    refresh = create_refresh_token(str(user.id))
    # Redireciona o navegador de volta ao front; o access_token é obtido via /refresh.
    redirect = RedirectResponse(url=f"{settings.frontend_url}/auth/callback?login=success")
    _set_refresh_cookie(redirect, refresh)
    return redirect


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request) -> TokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sem refresh token.")
    try:
        payload = decode_token(raw, expected_type="refresh")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido ou expirado.")

    access = create_access_token(payload["sub"])
    return TokenResponse(
        access_token=access,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=MeResponse)
def me(user=Depends(get_current_user)) -> MeResponse:
    ativos = user.modulos_ativos
    return MeResponse(
        usuario=UsuarioPublico.model_validate(user),
        modulos={m: (m in ativos) for m in MODULOS},
    )


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(REFRESH_COOKIE, path="/auth")
    return {"detail": "Sessão encerrada."}
