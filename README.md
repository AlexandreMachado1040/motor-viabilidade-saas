# Motor de Viabilidade — SaaS modular

Plataforma SaaS para estudos de viabilidade de sistemas de energia (solar, BESS,
geradores, GridZero, híbridos), com **motor de cálculo modular em Python** e
**plataforma web com autenticação e licenciamento por módulo**.

> **Navegação privada:** todo front de módulo exige login **e** a licença do
> módulo correspondente. Não há área pública de módulo.

## Estrutura

```
.
├── src/motor_viabilidade/   # motor de cálculo modular (1 pasta por módulo)
├── backend/                 # API FastAPI (auth social + JWT, licenças, admin)
├── frontend/                # SPA Vite + React + TypeScript
├── .docs/                   # material de referência (scripts/planilhas originais)
└── CHECKPOINT.md            # estado do projeto e próximos passos
```

## Pré-requisitos

- Python 3.12+
- Node 20+ / npm

## Rodando localmente

**Backend** (porta 8000):
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
copy .env.example .env                               # preencha os segredos
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend** (porta 5173):
```bash
cd frontend
npm install
copy .env.example .env                               # VITE_API_URL
npm run dev
```

Docs da API: http://localhost:8000/docs · App: http://localhost:5173

## Autenticação

Login social **Google/Microsoft** (OAuth2/OIDC via Authlib); o backend emite o
**próprio JWT** (access em memória + refresh em cookie httpOnly). Acesso a cada
módulo é controlado por `motor_viabilidade.LicencaModulos` (tabela
`module_licenses`) — `require_module(<m>)` no backend e `<ProtectedRoute>` no front.

> Para testes locais sem OAuth, há um login de desenvolvimento gatilhado por
> `DEV_LOGIN_ENABLED=true` (**nunca** habilitar em produção).

## Motor de cálculo

```bash
cd src
python -m motor_viabilidade --ambos      # estudo híbrido + GridZero
```

## Testes

```bash
cd frontend && npm run test:run          # Vitest
```

## Deploy

- **Frontend** → Cloudflare Pages (build estático `frontend/dist`).
- **Backend** → host Python (Render/Railway/Fly). Não roda em Cloudflare Workers.
  Após hospedar, aponte `VITE_API_URL` do frontend para a URL do backend.
