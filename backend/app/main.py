"""Aplicação FastAPI: middlewares, CORS e roteamento da API de autenticação."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .admin.router import router as admin_router
from .auth.router import router as auth_router
from .core.config import settings
from .db.init_db import init_db
from .licenca.router import router as licenca_router
from .modulos.load.router import router as load_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Conveniência de desenvolvimento. Em produção use Alembic e defina
    # AUTO_CREATE_TABLES=false no .env.
    if settings.auto_create_tables:
        init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# SessionMiddleware é exigido pelo Authlib para guardar o `state` do OAuth
# durante o redirecionamento ao provedor.
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,   # necessário para o cookie de refresh
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(licenca_router)
app.include_router(admin_router)
app.include_router(load_router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
