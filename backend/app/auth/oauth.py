"""Registro de provedores OAuth2/OIDC (Google e Microsoft) via Authlib."""
from __future__ import annotations

from authlib.integrations.starlette_client import OAuth

from ..core.config import settings

oauth = OAuth()

if settings.google_enabled:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if settings.microsoft_enabled:
    oauth.register(
        name="microsoft",
        client_id=settings.microsoft_client_id,
        client_secret=settings.microsoft_client_secret,
        server_metadata_url=(
            f"https://login.microsoftonline.com/{settings.microsoft_tenant}"
            "/v2.0/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile"},
    )


def provedor_disponivel(provider: str) -> bool:
    return getattr(oauth, provider, None) is not None
