# Módulo de Autenticação — Frontend (Vite + React + TS)

SPA de acesso ao Motor de Viabilidade: login social, contexto de sessão e
roteamento protegido por autenticação **e por módulo licenciado**.

## Estrutura

```
frontend/src/
├── main.tsx                ← bootstrap React
├── App.tsx                 ← rotas (login, callback, dashboard)
├── styles.css
├── types.ts                ← tipos compartilhados (Usuario, MeResponse…)
├── api/
│   └── client.ts           ← axios + interceptors (Bearer, refresh em 401)
├── auth/
│   ├── AuthContext.tsx     ← provider de sessão (login/logout/recarregar)
│   ├── useAuth.ts          ← hook de acesso ao contexto
│   └── ProtectedRoute.tsx  ← exige login (e opcionalmente um módulo)
└── pages/
    ├── LoginPage.tsx       ← botões Google/Microsoft
    ├── CallbackPage.tsx    ← retorno do OAuth → recarrega sessão
    └── DashboardPage.tsx   ← perfil + módulos licenciados
```

## Rodando

```bash
cd frontend
npm install
copy .env.example .env        # VITE_API_URL=http://localhost:8000
npm run dev                   # http://localhost:5173
```

O backend (FastAPI) precisa estar no ar em `VITE_API_URL`. O CORS do backend já
permite `http://localhost:5173` com `allow_credentials` (cookie de refresh).

## Detalhes de segurança

- O **access token vive em memória** (não em `localStorage`), reduzindo XSS.
- O **refresh token** trafega em **cookie httpOnly** definido pelo backend.
- Em `401`, o interceptor tenta **um** refresh e repete a requisição.

## Proteger uma rota por módulo

```tsx
<ProtectedRoute modulo="gridzero">
  <GridZeroPage />
</ProtectedRoute>
```
