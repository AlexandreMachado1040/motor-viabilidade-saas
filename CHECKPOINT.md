# CHECKPOINT — Motor de Viabilidade (SaaS modular)

> Última atualização: 16/06/2026 · Ponto de retomada do trabalho.

## Visão geral

Transformação do estudo de viabilidade (planilha + scripts em `.docs/`) num
**SaaS modular**: um motor de cálculo em Python (pacote modularizado, uma pasta
por módulo) + uma plataforma web com **autenticação e licenciamento por módulo**.

Regra de produto central: **cada módulo é navegação privada/autenticada**, nunca
pública. O acesso a qualquer front de módulo exige login **e** a licença do
módulo correspondente. As abas CAPA e README da planilha original ficam de fora.

## Estrutura atual

```
yuriNEW/
├── .docs/                     # material de referência (planilhas, scripts originais)
├── src/motor_viabilidade/     # motor modularizado (18 subpacotes + GridZero)  ✅
├── backend/                   # API FastAPI (auth + licença + admin)            ✅
│   ├── app/
│   │   ├── core/  (config, security/JWT)
│   │   ├── db/    (User, ModuleLicense)
│   │   ├── auth/  (OAuth social + JWT próprio)
│   │   ├── licenca/ (ponte → motor_viabilidade.LicencaModulos)
│   │   └── admin/ (painel de licenças)
│   └── migrations/ (Alembic: 2 revisões aplicadas)
└── frontend/                  # SPA Vite + React + TS                           ✅
    └── src/ (api, auth, pages, test/ → Vitest)
```

## O que está PRONTO e VALIDADO

| Bloco | Estado | Verificação |
|---|---|---|
| Motor modularizado (`src/motor_viabilidade`) | ✅ | `python -m motor_viabilidade --ambos` roda híbrido + GridZero |
| Backend auth (FastAPI) | ✅ | TestClient: health/providers/login/me/refresh |
| Login social + JWT próprio (Google/Microsoft) | ✅ | fluxo híbrido; refresh em cookie httpOnly |
| Licença por módulo (ponte com `LicencaModulos`) | ✅ | `/licenca/me`, guard `require_module` (403/200) |
| Painel admin (`/admin`) | ✅ | bootstrap via `ADMIN_EMAILS`; toggle de módulos |
| Migrações Alembic | ✅ | `408afe7b86be` (schema) + `09020a684b4f` (is_admin) |
| Frontend (login, callback, dashboard, admin) | ✅ | `npm run build` (tsc strict) verde |
| Testes Vitest | ✅ | 10/10 (`ProtectedRoute` + token store) |
| **MOD 1 InputLoad — backend** (`/modulos/load/*`) | ✅ | guard 403 sem licença; exemplo 12×24; validar totais/erros |
| **MOD 1 InputLoad — front privado** (`/modulos/load`) | ✅ | grid 12×24 + colagem TSV pt-BR; KPIs; validação no servidor |

## Decisões de arquitetura

- **Backend**: FastAPI + SQLAlchemy 2.0 + Alembic + SQLite (dev).
- **Auth**: OAuth2 social (Google/Microsoft via Authlib) → **o backend emite o
  próprio JWT** (access em memória no front, refresh em cookie httpOnly).
- **Frontend**: Vite + React + TypeScript (strict) + React Router + axios.
- **Licenciamento**: tabela `module_licenses` espelha as flags de
  `motor_viabilidade.LicencaModulos`; `require_module(<m>)` no backend e
  `<ProtectedRoute modulo="<m>">` no front.
- **Navegação privada**: todo front de módulo fica atrás de `ProtectedRoute`.

## Publicação (17/06/2026)

- **GitHub:** `AlexandreMachado1040/motor-viabilidade-saas` — privado, branch `main`.
  Auth do `gh` via keyring está quebrada; pushes exigem token com escopo `repo`
  (clássico) — fine-grained somente-leitura dá `403` no push.
- **Cloudflare Pages:** https://motor-viabilidade-saas.pages.dev (frontend estático).
  Projeto `motor-viabilidade-saas`. Redeploy: `wrangler pages deploy frontend/dist
  --project-name motor-viabilidade-saas --branch main`.
- **Pendente p/ a app funcionar na nuvem:** hospedar o backend (host Python) e
  apontar `VITE_API_URL` + `CORS_ORIGINS`/`FRONTEND_URL` para os domínios de produção.

## Pendência externa (sua)

- Preencher credenciais OAuth em `backend/.env` (Google Cloud / Azure Portal).
  Sem isso a API sobe, mas o login social não completa.

## MOD 1 `InputLoad` — CONCLUÍDO ✅

- Backend `app/modulos/load/` (`POST /validar`, `GET /exemplo`) + `app/integracao/motor.py`
  (bootstrap de `sys.path` p/ importar `motor_viabilidade`). Rotas privadas via
  `require_module("load")`.
- Frontend `pages/modulos/LoadPage.tsx` (rota privada `/modulos/load`): grid 12×24
  editável, colagem TSV pt-BR, energia mensal, KPIs e validação no servidor.
  O chip "load" do dashboard navega para a tela quando licenciado.
- **Upload de memória de massa** (`loadUpload.ts`): auto-detecta export de
  distribuidora (`dem`/`cons`, Latin-1, `;`, decimal vírgula, coluna "Postos
  horários" → Ponta/FP), grade 12×24, ou fallback genérico. CSV/TSV + Excel
  (SheetJS). Agrega em 12×24 + energia mensal. Validado com arquivo real
  (35.136 leituras / 15 min). Dados de cliente em `.docs/massa/` (gitignored).

## Modo demonstração (Cloudflare) ✅

- Flag `VITE_DEMO_MODE` (build): bypassa login (usuário convidado + todos os
  módulos) e roda o InputLoad 100% no navegador (exemplo embutido + validação e
  upload client-side). Dev local segue com login + backend reais.
- Build demo: `cd frontend && VITE_DEMO_MODE=true npm run build` →
  `wrangler pages deploy dist --project-name motor-viabilidade-saas --branch main`.
- Para voltar ao modo com login: rebuildar SEM a flag e redeployar.

## Servidores locais (dev)

- Backend: `cd backend && uvicorn app.main:app --reload` (porta 8000).
- Frontend: `cd frontend && npm run dev` (porta 5173). DEV_LOGIN_ENABLED=true →
  caixa "Entrar (dev)" na tela de login.

## PRÓXIMO PASSO (retomar aqui) — Front do MOD 2 `InputGrid`

Tarifas/encargos da distribuidora (+ API ANEEL). Mesmo padrão privado:
1. Backend `app/modulos/grid/` (`require_module("grid")`): endpoints para validar
   tarifas e (opcional) buscar via `ClienteAPIANEEL`.
2. Frontend `pages/modulos/GridPage.tsx`, rota privada `/modulos/grid`; registrar
   em `FRONTS` no dashboard.

Padrão reutilizável já estabelecido pelo MOD 1 (integracao/motor.py, schemas,
service, router com guard; página com KPIs + validação no servidor).
