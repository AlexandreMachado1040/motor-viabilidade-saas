"""Testes de validade (`expires_at`) de `ModuleLicense`.

Achado da priorização de gaps (dominios/licenciamento-habilitacao/spec.md):
`ModuleLicense` não tinha coluna de validade — uma licença, uma vez concedida
(manual ou por prova), nunca expirava. Adicionamos `expires_at` (NULL = nunca
expira, preserva todo comportamento pré-existente) e centralizamos a checagem
em `User.modulos_ativos` (db/models.py), que é a única fonte lida por
`require_module()`, `/auth/me`, o painel admin e a ponte pro motor
(`licenca/service.py`) — corrigir ali corrige todos os consumidores de uma vez.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import ModuleLicense, User
from tests.conftest import auth_headers


def _licenciar(db: Session, user: User, modulo: str, *,
                expires_at: dt.datetime | None = None, enabled: bool = True) -> ModuleLicense:
    lic = ModuleLicense(user_id=user.id, module=modulo, enabled=enabled,
                         source="manual", expires_at=expires_at)
    db.add(lic)
    db.commit()
    db.refresh(user)
    return lic


def test_licenca_sem_expires_at_nunca_expira(db_session, usuario):
    """NULL preserva o comportamento de toda licença já existente."""
    _licenciar(db_session, usuario, "gridzero", expires_at=None)
    assert "gridzero" in usuario.modulos_ativos


def test_licenca_com_expires_at_no_futuro_fica_ativa(db_session, usuario):
    futuro = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(days=30)
    _licenciar(db_session, usuario, "gridzero", expires_at=futuro)
    assert "gridzero" in usuario.modulos_ativos


def test_licenca_com_expires_at_no_passado_nao_conta_mais(db_session, usuario):
    passado = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(days=1)
    _licenciar(db_session, usuario, "gridzero", expires_at=passado)
    assert "gridzero" not in usuario.modulos_ativos


def test_licenca_expirada_nao_reaparece_mesmo_com_enabled_true(db_session, usuario):
    """`enabled=True` sozinho não basta mais — é achado do bug original:
    expirar não exigia zerar `enabled` manualmente."""
    passado = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(seconds=1)
    lic = _licenciar(db_session, usuario, "gridzero", expires_at=passado, enabled=True)
    assert lic.enabled is True
    assert "gridzero" not in usuario.modulos_ativos


def test_endpoint_protegido_libera_com_licenca_valida(client, db_session, usuario):
    _licenciar(db_session, usuario, "gridzero", expires_at=None)
    r = client.get("/licenca/exemplo/gridzero", headers=auth_headers(usuario))
    assert r.status_code == 200


def test_endpoint_protegido_bloqueia_licenca_expirada_com_mensagem_especifica(client, db_session, usuario):
    passado = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(days=1)
    _licenciar(db_session, usuario, "gridzero", expires_at=passado)
    r = client.get("/licenca/exemplo/gridzero", headers=auth_headers(usuario))
    assert r.status_code == 403
    assert "expirou" in r.json()["detail"].lower()


def test_endpoint_protegido_bloqueia_modulo_nunca_contratado_com_mensagem_generica(client, usuario):
    r = client.get("/licenca/exemplo/gridzero", headers=auth_headers(usuario))
    assert r.status_code == 403
    assert "não contratado" in r.json()["detail"].lower()


# ── Regressão (achado Codex, 14/09): normalização de timezone ──────────────
#
# `expires_at` volta do SQLite sempre NAIVE (dialeto não guarda tzinfo, só o
# valor de parede). A correção normaliza pra UTC-naive já na ATRIBUIÇÃO
# (`ModuleLicense._normalizar_expires_at`, um `@validates` do SQLAlchemy),
# não só na hora de comparar — porque o dano de um datetime aware em fuso
# não-UTC acontece na GRAVAÇÃO (SQLite grava a hora de parede tal como veio,
# sem converter), não na leitura. Os dois testes abaixo cobrem os dois efeitos
# dessa correção:


def test_expires_at_aware_e_normalizado_para_naive_ja_na_atribuicao(db_session, usuario):
    """Antes da correção: um `expires_at` AWARE ficava aware em memória até
    passar por commit+refresh — comparar contra um "agora" naive nesse
    intervalo levantava `TypeError: can't compare offset-naive and
    offset-aware datetimes`. Agora o `@validates` normaliza no instante do
    `ModuleLicense(...)`, antes de qualquer flush."""
    futuro_aware = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    lic = ModuleLicense(user_id=usuario.id, module="gridzero", enabled=True,
                         source="manual", expires_at=futuro_aware)
    usuario.licenses.append(lic)  # sem commit/refresh
    assert lic.expires_at.tzinfo is None  # já normalizado, não mais aware
    assert "gridzero" in usuario.modulos_ativos  # não deve lançar TypeError


def test_expires_at_com_offset_nao_utc_ja_vencido_e_detectado_como_expirado(db_session, usuario):
    """Antes da correção: `.replace(tzinfo=None)` descartava o offset sem
    converter pra UTC primeiro. Uma licença vencida há 1h em UTC, mas gravada
    com offset +03:00 (hora de parede 3h "no futuro" em relação à hora UTC
    equivalente), voltava do SQLite como naive e comparava como ainda ativa —
    reproduzido e confirmado antes do fix. `astimezone(utc)` antes de
    descartar o `tzinfo` corrige isso."""
    agora_utc = dt.datetime.now(dt.timezone.utc)
    vencido_utc = agora_utc - dt.timedelta(hours=1)
    vencido_offset_leste = vencido_utc.astimezone(dt.timezone(dt.timedelta(hours=3)))
    assert vencido_offset_leste.hour != vencido_utc.hour  # confirma que o teste testa o que diz testar

    _licenciar(db_session, usuario, "gridzero", expires_at=vencido_offset_leste)
    assert "gridzero" not in usuario.modulos_ativos


def test_expirada_aceita_agora_explicito_naive_e_aware(db_session, usuario):
    lic = _licenciar(db_session, usuario, "gridzero",
                      expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=1))
    referencia_futura_naive = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=2)
    referencia_futura_aware = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
    assert lic.expirada(referencia_futura_naive) is True
    assert lic.expirada(referencia_futura_aware) is True


def test_expires_at_com_offset_nao_utc_via_core_update_tambem_e_normalizado(db_session, usuario):
    """Achado Codex (2ª rodada): `@validates` só dispara em atribuição via
    atributo do ORM (`lic.expires_at = valor`) — um `UPDATE` via SQLAlchemy
    Core (`update(ModuleLicense).values(...)`, usado por operações em lote que
    não passam pelo objeto instrumentado) não aciona esse validator. Sem o
    `UTCDateTime` (TypeDecorator que normaliza no bind, não no atributo), esse
    caminho reproduzia o mesmo bug do offset não-UTC mesmo com o validator no
    lugar — confirmado antes desta correção."""
    lic = _licenciar(db_session, usuario, "gridzero", expires_at=None)

    agora_utc = dt.datetime.now(dt.timezone.utc)
    vencido_offset_leste = (agora_utc - dt.timedelta(hours=1)).astimezone(dt.timezone(dt.timedelta(hours=3)))

    db_session.execute(
        update(ModuleLicense).where(ModuleLicense.id == lic.id).values(expires_at=vencido_offset_leste)
    )
    db_session.commit()

    recarregado = db_session.scalar(select(User).where(User.id == usuario.id))
    assert "gridzero" not in recarregado.modulos_ativos
