# Migrações (Alembic)

```bash
cd backend
alembic upgrade head                          # aplica todas as migrações
alembic revision --autogenerate -m "mudança"  # gera nova migração a partir dos modelos
alembic downgrade -1                           # desfaz a última
alembic current                                # revisão aplicada
alembic history                                # histórico
```

A URL do banco vem de `app.core.config.settings` (via `.env`); não é duplicada
no `alembic.ini`. Em produção, use `alembic upgrade head` no deploy e deixe
`AUTO_CREATE_TABLES=false` no `.env` para que o `create_all` não concorra com as
migrações.
