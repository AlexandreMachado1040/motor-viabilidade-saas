"""Testes do MOD 11 — InputGridZero (POST /modulos/gridzero/validar).

Diferente dos MOD 3-9: InputGridZero TEM `.validar()` no motor, e o
`/validar` aqui roda o cálculo financeiro completo (CalculadoraGridZero),
não só ecoa um derivado simples — os valores de referência abaixo (payload
vazio = defaults do motor) foram capturados rodando
`CalculadoraGridZero(InputGridZero()).calcular()` direto, antes de escrever
os testes.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import ModuleLicense, User
from tests.conftest import auth_headers


def _licenciar(db: Session, user: User, modulo: str) -> None:
    db.add(ModuleLicense(user_id=user.id, module=modulo, enabled=True, source="manual"))
    db.commit()
    db.refresh(user)


def test_validar_payload_vazio_roda_calculo_completo(client, db_session, usuario):
    _licenciar(db_session, usuario, "gridzero")
    r = client.post("/modulos/gridzero/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    # potencia_cc_kwp = 75 kW AC * 1.32 sobredimensionamento
    assert body["potencia_cc_kwp"] == pytest.approx(99.0)
    # capex_total_r = 99 kWp * R$3000/kWp
    assert body["capex_total_r"] == pytest.approx(297_000.0)
    assert body["autoconsumo_pct"] == pytest.approx(30.75, abs=0.01)
    assert body["simultaneidade_pct"] == pytest.approx(100.0, abs=0.01)
    assert body["vpl_r"] == pytest.approx(1_463_988.30, abs=1)
    assert body["payback_anos"] == pytest.approx(1.8866, abs=0.001)
    assert len(body["fc_nominal"]) == 26   # ano 0 + 25 anos de projeto
    assert len(body["fc_acumulado"]) == 26


def test_validar_rejeita_demanda_horaria_com_menos_de_24_valores(client, db_session, usuario):
    _licenciar(db_session, usuario, "gridzero")
    r = client.post(
        "/modulos/gridzero/validar",
        json={"demanda_horaria_kw": [50.0] * 23},
        headers=auth_headers(usuario),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is False
    assert any("demanda_horaria_kw" in e for e in body["erros"])


def test_validar_rejeita_perfil_solar_com_mais_de_24_valores(client, db_session, usuario):
    _licenciar(db_session, usuario, "gridzero")
    r = client.post(
        "/modulos/gridzero/validar",
        json={"perfil_solar_norm": [0.5] * 25},
        headers=auth_headers(usuario),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is False
    assert any("perfil_solar_norm" in e for e in body["erros"])


def test_validar_rejeita_potencia_ac_kw_nao_positiva(client, db_session, usuario):
    _licenciar(db_session, usuario, "gridzero")
    r = client.post(
        "/modulos/gridzero/validar", json={"potencia_ac_kw": 0}, headers=auth_headers(usuario)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is False
    assert any("potencia_ac_kw" in e for e in body["erros"])


def test_validar_rejeita_capex_kwp_nao_positivo(client, db_session, usuario):
    _licenciar(db_session, usuario, "gridzero")
    r = client.post(
        "/modulos/gridzero/validar", json={"capex_kwp": -1}, headers=auth_headers(usuario)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is False
    assert any("capex_kwp" in e for e in body["erros"])


def test_validar_coleta_multiplos_erros_de_uma_vez(client, db_session, usuario):
    _licenciar(db_session, usuario, "gridzero")
    r = client.post(
        "/modulos/gridzero/validar",
        json={"potencia_ac_kw": 0, "capex_kwp": 0, "demanda_horaria_kw": []},
        headers=auth_headers(usuario),
    )
    body = r.json()
    assert body["valido"] is False
    assert len(body["erros"]) == 3


def test_preset_concessionaria_sobrescreve_tarifa_manual(client, db_session, usuario):
    """Achado ao ler o motor: __post_init__ aplica o preset por cima de
    qualquer te_kwh/tusd_kwh customizado no payload, a menos que
    preset_concessionaria='manual' — comportamento do motor, não um bug
    deste endpoint; o teste documenta essa armadilha."""
    _licenciar(db_session, usuario, "gridzero")
    r = client.post(
        "/modulos/gridzero/validar",
        json={"preset_concessionaria": "cpfl_b3", "te_kwh": 999.0},
        headers=auth_headers(usuario),
    )
    body = r.json()
    assert body["valido"] is True
    # tarifa_kwh reflete o preset (0.287+0.388)*fator, não o te_kwh=999 enviado
    assert body["tarifa_kwh"] == pytest.approx(0.8303, abs=0.001)


def test_endpoint_bloqueado_sem_licenca_do_modulo(client, usuario):
    r = client.post("/modulos/gridzero/validar", json={}, headers=auth_headers(usuario))
    assert r.status_code == 403
