"""Testes do MOD 2 — InputGrid (POST/GET /modulos/grid/*).

Primeiro módulo replicado do padrão de MOD 1 — InputLoad (item de
modularização em dominios/motor-viabilidade/spec.md). Ao contrário de
InputLoad, InputGrid é um dataclass plano do motor sem `.validar()` — não há
estrutura variável (meses/horas) pra rejeitar, só os dois derivados
(tarifa_ponta, tarifa_fp) que o motor calcula via @property.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import ModuleLicense, User
from tests.conftest import auth_headers


def _licenciar_grid(db: Session, user: User) -> None:
    db.add(ModuleLicense(user_id=user.id, module="grid", enabled=True, source="manual"))
    db.commit()
    db.refresh(user)


def test_validar_com_payload_vazio_usa_defaults_e_calcula_tarifas(client, db_session, usuario):
    _licenciar_grid(db_session, usuario)
    r = client.post("/modulos/grid/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    # defaults: tusd_ponta=1.326 + te_ponta=0.379 = 1.705; tusd_fp=0.118 + te_fp=0.232 = 0.350
    assert body["tarifa_ponta"] == 1.705
    assert body["tarifa_fp"] == 0.35


def test_validar_com_payload_customizado_recalcula_tarifas(client, db_session, usuario):
    _licenciar_grid(db_session, usuario)
    r = client.post(
        "/modulos/grid/validar",
        json={"tusd_ponta": 1.0, "te_ponta": 0.5, "tusd_fp": 0.2, "te_fp": 0.1},
        headers=auth_headers(usuario),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tarifa_ponta"] == pytest.approx(1.5)
    assert body["tarifa_fp"] == pytest.approx(0.3)


def test_endpoint_bloqueado_sem_licenca_do_modulo(client, usuario):
    r = client.post("/modulos/grid/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403


def test_exemplo_devolve_dados_da_planilha_original(client, db_session, usuario):
    _licenciar_grid(db_session, usuario)
    r = client.get("/modulos/grid/exemplo", headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["concessionaria"] == "Cemig-D"
    assert body["subgrupo"] == "A4"
    assert body["modalidade"] == "Verde"


def test_exemplo_bloqueado_sem_licenca_do_modulo(client, usuario):
    r = client.get("/modulos/grid/exemplo", headers=auth_headers(usuario))
    assert r.status_code == 403


# ── Simulador de modalidades tarifárias ──────────────────────────────────────

def test_exemplo_tarifas_traz_doze_meses_e_tres_modalidades(client, db_session, usuario):
    _licenciar_grid(db_session, usuario)
    r = client.get("/modulos/grid/exemplo-tarifas", headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert len(body["demanda_fp_kw"]) == 12
    assert body["azul"]["demanda_ponta"] == pytest.approx(28.41)
    assert body["baixa_tensao"] is None


def test_simular_tarifas_do_exemplo_recomenda_a_mais_barata(client, db_session, usuario):
    _licenciar_grid(db_session, usuario)
    h = auth_headers(usuario)
    exemplo = client.get("/modulos/grid/exemplo-tarifas", headers=h).json()
    r = client.post("/modulos/grid/simular-tarifas", json=exemplo, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    custos = {m["modalidade"]: m["custo_anual"] for m in body["modalidades"]}
    assert set(custos) == {"Convencional", "Azul", "Verde"}
    assert body["recomendada"] == min(custos, key=custos.get)
    assert body["economia_vs_atual"][body["recomendada"]] == 0
    assert {s["modalidade"] for s in body["demandas_sugeridas"]} == {"Convencional", "Azul", "Verde"}


def test_simular_tarifas_devolve_erros_de_estrutura(client, db_session, usuario):
    _licenciar_grid(db_session, usuario)
    r = client.post(
        "/modulos/grid/simular-tarifas",
        json={"demanda_ponta_kw": [1.0] * 11, "demanda_fp_kw": [0.0] * 12,
              "consumo_ponta_kwh": [0.0] * 12, "consumo_fp_kwh": [0.0] * 12},
        headers=auth_headers(usuario),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is False
    assert "demanda_ponta_kw deve ter 12 meses (recebido: 11)." in body["erros"]
    assert "Informe as tarifas de pelo menos uma modalidade." in body["erros"]


def test_simular_tarifas_rejeita_tarifa_negativa(client, db_session, usuario):
    _licenciar_grid(db_session, usuario)
    r = client.post(
        "/modulos/grid/simular-tarifas",
        json={"demanda_ponta_kw": [0.0] * 12, "demanda_fp_kw": [0.0] * 12,
              "consumo_ponta_kwh": [0.0] * 12, "consumo_fp_kwh": [0.0] * 12,
              "baixa_tensao": {"consumo": -1}},
        headers=auth_headers(usuario),
    )
    assert r.status_code == 422


def test_simulador_bloqueado_sem_licenca(client, usuario):
    r = client.post("/modulos/grid/simular-tarifas", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403
