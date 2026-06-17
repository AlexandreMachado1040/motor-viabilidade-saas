# Módulo de Autenticação — Backend (FastAPI)

API de autenticação **social (Google/Microsoft) + JWT próprio**, com controle de
acesso por módulo integrado ao `motor_viabilidade.LicencaModulos`.

## Por que híbrido (social + JWT próprio)?

O provedor externo (Google/Azure AD) **autentica a identidade**; o seu backend
**emite o próprio JWT** (access + refresh) que protege todas as rotas da API.
Isso desacopla a API dos provedores e permite anexar as licenças de módulo do
SaaS ao token/usuário.

```
Navegador ──/auth/login/{provider}──▶ Backend ──▶ Provedor (Google/MS)
   ▲                                                     │
   └──────── /auth/callback (cookie refresh) ◀───────────┘
Front ──POST /auth/refresh (cookie)──▶ access_token  ──Bearer──▶ rotas protegidas
```

## Estrutura

```
backend/app/
├── main.py                 ← app FastAPI, CORS, SessionMiddleware, routers
├── core/
│   ├── config.py           ← settings via .env (pydantic-settings)
│   └── security.py         ← cria/valida JWT (PyJWT)
├── db/
│   ├── base.py             ← engine/sessão SQLAlchemy
│   ├── models.py           ← User + ModuleLicense (espelha LicencaModulos)
│   └── init_db.py          ← create_all (skeleton)
├── auth/
│   ├── oauth.py            ← registro Authlib (google, microsoft)
│   ├── schemas.py          ← Pydantic
│   ├── service.py          ← upsert de usuário + licenças padrão
│   ├── dependencies.py     ← get_current_user, require_module(...)
│   └── router.py           ← /auth/login, /callback, /refresh, /me, /logout
└── licenca/
    ├── service.py          ← ponte → motor_viabilidade.LicencaModulos
    └── router.py           ← /licenca/me + exemplo protegido por módulo
```

## Rodando

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows
# source .venv/bin/activate                           # Linux/macOS
pip install -r requirements.txt
copy .env.example .env                                # preencha as credenciais
uvicorn app.main:app --reload
```

Docs interativas: http://localhost:8000/docs · Health: `/health`

## Configurar OAuth

- **Google**: console.cloud.google.com → Credentials → OAuth client (Web).
  Redirect URI: `http://localhost:8000/auth/callback/google`
- **Microsoft/Azure AD**: portal.azure.com → App registrations.
  Redirect URI: `http://localhost:8000/auth/callback/microsoft`.
  Use `MICROSOFT_TENANT=common` (multi-tenant) ou o tenant da ANEEL
  (`67ffc8c1-...`, mesmo de `ConfigAPIANEEL`) para single-tenant.

Sem credenciais, os endpoints de login retornam `503` e o front desabilita os
botões — o restante da API sobe normalmente.

## Integração com o motor

`licenca/service.py:montar_licenca()` converte os módulos do usuário em um
`motor_viabilidade.LicencaModulos`. Para que o import funcione, exponha o pacote:

```bash
# a partir da raiz do projeto
set PYTHONPATH=%CD%\src           # Windows
# export PYTHONPATH=$PWD/src       # Linux/macOS
```

Se o pacote não estiver no path, a ponte cai num `SimpleNamespace` com as mesmas
flags (sem quebrar a API).

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/auth/providers` | provedores configurados (para o front) |
| GET | `/auth/login/{provider}` | inicia o login social |
| GET | `/auth/callback/{provider}` | retorno do provedor → cookie de refresh |
| POST | `/auth/refresh` | novo access token (via cookie) |
| GET | `/auth/me` | usuário atual + flags de módulos |
| POST | `/auth/logout` | encerra a sessão |
| GET | `/licenca/me` | flags no formato `LicencaModulos` |
| GET | `/licenca/exemplo/gridzero` | exemplo protegido por `require_module("gridzero")` |
