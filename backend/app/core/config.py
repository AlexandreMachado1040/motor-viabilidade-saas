"""Configuração central da aplicação (carregada de variáveis de ambiente/.env)."""
from __future__ import annotations

from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Motor de Viabilidade — Autenticação"

    # URLs
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    # Segredos
    session_secret: str = "troque-este-segredo-de-sessao"
    jwt_secret: str = "troque-este-segredo-do-jwt"
    jwt_algorithm: str = "HS256"

    # Banco
    database_url: str = "sqlite:///./auth.db"
    # Em produção com Alembic, defina False para o create_all não concorrer.
    auto_create_tables: bool = True

    # Tokens
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # Google
    google_client_id: str = ""
    google_client_secret: str = ""

    # Microsoft / Azure AD
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant: str = "common"

    # Login de desenvolvimento (NÃO usar em produção): emite sessão sem OAuth.
    dev_login_enabled: bool = False

    # CORS (string separada por vírgula → lista)
    cors_origins: str = "http://localhost:5173"

    # Administradores (e-mails separados por vírgula)
    admin_emails: str = ""

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @cached_property
    def admin_emails_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def microsoft_enabled(self) -> bool:
        return bool(self.microsoft_client_id and self.microsoft_client_secret)


settings = Settings()
