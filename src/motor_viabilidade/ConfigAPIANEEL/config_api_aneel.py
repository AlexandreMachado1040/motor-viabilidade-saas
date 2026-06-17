"""Configuração de autenticação OAuth2 para o BI da ANEEL (Dynamics 365)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConfigAPIANEEL:
    """
    Configuração de autenticação para o BI da ANEEL
    (Microsoft Dynamics 365 / Dataverse).

    O endpoint exige autenticação OAuth 2.0 via Azure AD (MSAL).
    Credenciais devem ser obtidas junto ao administrador do tenant ANEEL.
    """
    tenant_id:     str = "67ffc8c1-818a-4849-9314-1aa26812c317"
    client_id:     str = ""       # App registration na ANEEL
    client_secret: str = ""       # Secret do app registration
    base_url:      str = "https://csisolarcrmprod.crm16.dynamics.com"
    api_version:   str = "v9.2"
    order_id:      str = "ad670927-b765-f111-ab0c-002248e570e3"
    usar_cache:    bool = True
    cache_path:    str = "aneel_tarifas_cache.json"


__all__ = ["ConfigAPIANEEL"]
