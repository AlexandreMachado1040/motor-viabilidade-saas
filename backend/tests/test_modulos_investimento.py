"""Testes dos MOD 3, 4, 5, 6, 7, 8, 9 (solar, bess_ponta, gen_ponta, gen_form,
bess_form, new_grid, cf) — mesmo padrão de test_modulo_grid.py (MOD 2), agora
pra 7 módulos de uma vez.

Nenhum destes tem `.validar()` no motor (ao contrário de InputLoad) — os
testes focam em: (a) endpoint bloqueado sem licença, (b) payload vazio usa
defaults e calcula os derivados certos, (c) exemplo funciona quando existe
dado de referência, 404/503 nos módulos que a planilha original não cobre
(gen_ponta, gen_form, bess_form, new_grid não têm rota /exemplo — ver notas
nos respectivos routers).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ModuleLicense, User
from tests.conftest import auth_headers


def _licenciar(db: Session, user: User, modulo: str) -> None:
    db.add(ModuleLicense(user_id=user.id, module=modulo, enabled=True, source="manual"))
    db.commit()
    db.refresh(user)


# ── MOD 3 — solar ────────────────────────────────────────────────────────────


def test_solar_validar_payload_vazio(client, db_session, usuario):
    _licenciar(db_session, usuario, "solar")
    r = client.post("/modulos/solar/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    assert len(body["energia_gerada_mensal_kwh"]) == 12
    assert len(body["energia_injetada_mensal_kwh"]) == 12
    # sem potencia_gerada_kw/potencia_injetada_kw no payload -> tudo zero
    assert all(v == 0.0 for v in body["energia_gerada_mensal_kwh"])
    # data_estudo_ano=2024 default -> cronograma_transicao[2024] = 0.30
    assert body["periodo_transicao_vigente"] == 0.30


def test_solar_validar_calcula_energia_gerada_e_injetada(client, db_session, usuario):
    _licenciar(db_session, usuario, "solar")
    perfil_mes = [10.0] * 24
    r = client.post(
        "/modulos/solar/validar",
        json={
            "potencia_gerada_kw": [perfil_mes] * 12,
            "potencia_injetada_kw": [[-v for v in perfil_mes]] * 12,
        },
        headers=auth_headers(usuario),
    )
    assert r.status_code == 200
    body = r.json()
    # Dia típico: 24h × 10 kW = 240 kWh/dia; janeiro tem 31 dias, fevereiro 28.
    assert body["energia_gerada_mensal_kwh"][0] == 240.0 * 31
    assert body["energia_injetada_mensal_kwh"][0] == 240.0 * 31  # abs(-240) × 31
    assert body["energia_gerada_mensal_kwh"][1] == 240.0 * 28


def test_solar_bloqueado_sem_licenca(client, usuario):
    r = client.post("/modulos/solar/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403


def test_solar_exemplo_devolve_dados_da_planilha(client, db_session, usuario):
    _licenciar(db_session, usuario, "solar")
    r = client.get("/modulos/solar/exemplo", headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "São Paulo"
    assert body["modalidade_gd"] == "GDIII"


# ── MOD 4 — bess_ponta ───────────────────────────────────────────────────────


def test_bess_ponta_validar_payload_vazio(client, db_session, usuario):
    _licenciar(db_session, usuario, "bess_ponta")
    r = client.post("/modulos/bess_ponta/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    # default: energia_dod80_kwh=1598.05 * percentual_eol=0.60
    assert round(body["energia_eol_dod80_kwh"], 2) == round(1598.05 * 0.60, 2)


def test_bess_ponta_bloqueado_sem_licenca(client, usuario):
    r = client.post("/modulos/bess_ponta/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403


def test_bess_ponta_exemplo_devolve_dados_da_planilha(client, db_session, usuario):
    _licenciar(db_session, usuario, "bess_ponta")
    r = client.get("/modulos/bess_ponta/exemplo", headers=auth_headers(usuario))
    assert r.status_code == 200
    assert r.json()["capex_r"] == 5_526_000


# ── MOD 5 — gen_ponta ────────────────────────────────────────────────────────


def test_gen_ponta_validar_payload_vazio_sem_consumo_definido(client, db_session, usuario):
    _licenciar(db_session, usuario, "gen_ponta")
    r = client.post("/modulos/gen_ponta/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    # defaults têm consumo_max_lh=0.0 -> custo_diesel_kwh = 0.0
    assert body["custo_diesel_kwh"] == 0.0


def test_gen_ponta_validar_calcula_custo_diesel_kwh(client, db_session, usuario):
    _licenciar(db_session, usuario, "gen_ponta")
    r = client.post(
        "/modulos/gen_ponta/validar",
        json={"consumo_max_lh": 100.0, "custo_diesel_litro": 5.0, "potencia_kw": 250.0},
        headers=auth_headers(usuario),
    )
    assert r.status_code == 200
    # 100 L/h * R$5/L / 250 kW = R$2/kWh
    assert r.json()["custo_diesel_kwh"] == 2.0


def test_gen_ponta_bloqueado_sem_licenca(client, usuario):
    r = client.post("/modulos/gen_ponta/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403


# ── MOD 6 — gen_form ─────────────────────────────────────────────────────────


def test_gen_form_validar_payload_vazio(client, db_session, usuario):
    _licenciar(db_session, usuario, "gen_form")
    r = client.post("/modulos/gen_form/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    # InputGeradorFormador.custo_diesel_kwh() sempre devolve 0.0 (ver docstring do motor)
    assert body["custo_diesel_kwh"] == 0.0


def test_gen_form_bloqueado_sem_licenca(client, usuario):
    r = client.post("/modulos/gen_form/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403


# ── MOD 7 — bess_form ────────────────────────────────────────────────────────


def test_bess_form_validar_payload_vazio(client, db_session, usuario):
    _licenciar(db_session, usuario, "bess_form")
    r = client.post("/modulos/bess_form/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    assert r.json()["valido"] is True


def test_bess_form_bloqueado_sem_licenca(client, usuario):
    r = client.post("/modulos/bess_form/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403


# ── MOD 8 — new_grid ─────────────────────────────────────────────────────────


def test_new_grid_validar_payload_vazio_usa_default_capex(client, db_session, usuario):
    _licenciar(db_session, usuario, "new_grid")
    r = client.post("/modulos/new_grid/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    assert body["capex_r"] == 15_000_000.0


def test_new_grid_validar_com_capex_customizado(client, db_session, usuario):
    _licenciar(db_session, usuario, "new_grid")
    r = client.post(
        "/modulos/new_grid/validar", json={"capex_r": 1000.0}, headers=auth_headers(usuario)
    )
    assert r.status_code == 200
    assert r.json()["capex_r"] == 1000.0


def test_new_grid_bloqueado_sem_licenca(client, usuario):
    r = client.post("/modulos/new_grid/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403


# ── MOD 9 — cf (ParamsCF) ────────────────────────────────────────────────────


def test_cf_validar_payload_vazio_calcula_taxa_real(client, db_session, usuario):
    _licenciar(db_session, usuario, "cf")
    r = client.post("/modulos/cf/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    # (1+0.08)/(1+0.0393) - 1
    esperado = ((1 + 0.08) / (1 + 0.0393)) - 1
    assert round(body["taxa_desconto_real"], 6) == round(esperado, 6)


def test_cf_bloqueado_sem_licenca(client, usuario):
    r = client.post("/modulos/cf/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403


def test_cf_exemplo_devolve_dados_da_planilha(client, db_session, usuario):
    _licenciar(db_session, usuario, "cf")
    r = client.get("/modulos/cf/exemplo", headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["anos_projeto"] == 25
    assert body["taxa_desconto"] == 0.08
