"""Testes do MOD 10 — Summary (POST /modulos/summary/validar).

Diferente de todos os outros: não é um `InputXxx` isolado — o payload
compõe os schemas dos módulos já construídos (reaproveitados de
modulos/{load,grid,solar,bess_ponta,cf}/schemas.py), e o service roda o
EstudoViabilidade completo (carregar_load → carregar_grid → ... →
calcular_cf → gerar_summary).

O teste do cenário completo busca os payloads de exemplo dos próprios
endpoints /exemplo já existentes (load/grid/solar/bess_ponta) em vez de
reescrever as matrizes 12×24 à mão — também serve como teste de integração
de que os 4 endpoints /exemplo produzem payloads que a rota /validar de
summary aceita juntos sem erro de schema."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import ModuleLicense, User
from tests.conftest import auth_headers


def _licenciar(db: Session, user: User, *modulos: str) -> None:
    for m in modulos:
        db.add(ModuleLicense(user_id=user.id, module=m, enabled=True, source="manual"))
    db.commit()
    db.refresh(user)


def test_endpoint_bloqueado_sem_licenca_do_modulo(client, usuario):
    r = client.post(
        "/modulos/summary/validar",
        json={"load": {}, "grid": {}},
        headers=auth_headers(usuario),
    )
    assert r.status_code == 403


def test_validar_rejeita_load_estruturalmente_invalido(client, db_session, usuario):
    _licenciar(db_session, usuario, "summary")
    r = client.post(
        "/modulos/summary/validar",
        json={"load": {"demanda_kw": [[0.0] * 24] * 11}, "grid": {}},  # só 11 meses
        headers=auth_headers(usuario),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is False
    assert any("demanda_kw" in e for e in body["erros"])


def test_validar_so_load_e_grid_sem_modulo_de_investimento(client, db_session, usuario):
    """Sem nenhum módulo de investimento, cfs fica vazio — o motor define
    `proposta = [0]*(anos+1)` (não o baseline) nesse caso, então
    `fc_total = (proposta-baseline)+baseline = proposta = tudo zero`.
    VPL=0, TIR indefinida (nenhum fluxo positivo), payback=0 (achado ao
    rodar o motor direto antes de escrever este teste — documentado em
    dominios/financeiro-viabilidade-economica/spec.md, a identidade
    algébrica de estudo_viabilidade.py)."""
    _licenciar(db_session, usuario, "summary")
    demanda_kw = [[10.0] * 24] * 12
    payload = {
        "load": {
            "demanda_maxima_kw": 20.0,
            "demanda_kw": demanda_kw,
            "energia_ponta_kwh": [1000.0] * 12,
            "energia_fp_kwh": [2000.0] * 12,
        },
        "grid": {},
    }
    r = client.post("/modulos/summary/validar", json=payload, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    assert body["indicadores"]["vpl"] == 0.0
    assert body["indicadores"]["tir_pct"] is None
    assert body["indicadores"]["payback"] == 0
    assert body["custos"]["capex_total"] == 0.0
    assert body["modulos_ativos"]["solar"] is False
    assert body["modulos_ativos"]["load"] is True
    assert body["modulos_ativos"]["grid"] is True


def test_validar_cenario_completo_bate_com_motor_direto(client, db_session, usuario):
    """Reproduz o cenário de exemplo_planilha_original() (load+grid+solar+
    bess_ponta) via os próprios endpoints /exemplo, e confirma que o
    resultado bate com rodar EstudoViabilidade direto (valores capturados
    rodando o motor antes de escrever este teste)."""
    _licenciar(db_session, usuario, "summary", "load", "grid", "solar", "bess_ponta")

    load = client.get("/modulos/load/exemplo", headers=auth_headers(usuario)).json()
    grid = client.get("/modulos/grid/exemplo", headers=auth_headers(usuario)).json()
    solar = client.get("/modulos/solar/exemplo", headers=auth_headers(usuario)).json()
    bess_ponta = client.get("/modulos/bess_ponta/exemplo", headers=auth_headers(usuario)).json()

    payload = {"load": load, "grid": grid, "solar": solar, "bess_ponta": bess_ponta}
    r = client.post("/modulos/summary/validar", json=payload, headers=auth_headers(usuario))
    assert r.status_code == 200
    body = r.json()

    assert body["valido"] is True
    assert body["projeto"]["concessionaria"] == "Cemig-D"
    assert body["projeto"]["subgrupo"] == "A4"
    assert body["projeto"]["demanda_maxima_kw"] == pytest.approx(238.56)
    assert body["projeto"]["potencia_solar_kwp"] == pytest.approx(300.0)
    assert body["custos"]["capex_total"] == pytest.approx(6_411_000.0)
    # Até 15/09 era −7.972.861,60: o motor contava 1 dia de geração solar e 1
    # ciclo de BESS por mês. Com dias do mês, ciclos em dias úteis e limites
    # de consumo, e com economias ano a ano (degradação, Fio B por ano,
    # reajuste tarifário): −6.698.746,18 (BESS de R$ 5,5 mi para ~200 kWh/dia
    # de ponta).
    assert body["indicadores"]["vpl"] == pytest.approx(-6_698_746.18, abs=1)
    assert body["indicadores"]["tir_pct"] is None
    assert body["indicadores"]["payback"] is None
    assert body["indicadores"]["viavel"] is False
    assert body["modulos_ativos"] == {
        "load": True, "grid": True, "solar": True, "bess_ponta": True,
        "gen_ponta": False, "gen_form": False, "bess_form": False,
        "new_grid": False, "cf": True, "summary": True, "gridzero": False,
    }


# ── Fatura do simulador de tarifas como baseline ─────────────────────────────

def _payload_referencia(client, usuario) -> dict:
    h = auth_headers(usuario)
    return {
        "load": client.get("/modulos/load/exemplo", headers=h).json(),
        "grid": client.get("/modulos/grid/exemplo", headers=h).json(),
        "solar": client.get("/modulos/solar/exemplo", headers=h).json(),
        "bess_ponta": client.get("/modulos/bess_ponta/exemplo", headers=h).json(),
    }


def test_validar_com_fatura_do_simulador_muda_baseline_e_vpl(client, db_session, usuario):
    _licenciar(db_session, usuario, "summary", "load", "grid", "solar", "bess_ponta")
    h = auth_headers(usuario)
    payload = _payload_referencia(client, usuario)
    tarifas = client.get("/modulos/grid/exemplo-tarifas", headers=h).json()
    simulacao = client.post("/modulos/grid/simular-tarifas", json=tarifas, headers=h).json()
    custo_verde = next(m["custo_anual"] for m in simulacao["modalidades"] if m["modalidade"] == "Verde")

    r = client.post("/modulos/summary/validar",
                    json={**payload, "tarifas": tarifas, "modalidade": "verde"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["valido"] is True
    assert body["projeto"]["modalidade"] == "Verde"
    assert body["projeto"]["fonte_tarifas"] == "simulador"
    assert body["custos"]["opex_grid_anual"] == pytest.approx(custo_verde)
    assert body["indicadores"]["vpl"] != pytest.approx(-6_698_746.18, abs=1)


def test_validar_sem_tarifas_mantem_fonte_grid(client, db_session, usuario):
    _licenciar(db_session, usuario, "summary", "load", "grid", "solar", "bess_ponta")
    r = client.post("/modulos/summary/validar", json=_payload_referencia(client, usuario),
                    headers=auth_headers(usuario))
    assert r.json()["projeto"]["fonte_tarifas"] == "grid"


def test_validar_rejeita_modalidade_sem_tarifa_informada(client, db_session, usuario):
    _licenciar(db_session, usuario, "summary", "load", "grid", "solar", "bess_ponta")
    h = auth_headers(usuario)
    tarifas = client.get("/modulos/grid/exemplo-tarifas", headers=h).json()
    r = client.post("/modulos/summary/validar",
                    json={**_payload_referencia(client, usuario), "tarifas": tarifas, "modalidade": "baixa_tensao"},
                    headers=h)
    body = r.json()
    assert body["valido"] is False
    assert body["erros"] == ["Informe as tarifas da modalidade Baixa Tensão."]


def test_validar_exige_tarifas_e_modalidade_juntas(client, db_session, usuario):
    _licenciar(db_session, usuario, "summary", "load", "grid", "solar", "bess_ponta")
    h = auth_headers(usuario)
    r = client.post("/modulos/summary/validar",
                    json={**_payload_referencia(client, usuario), "modalidade": "azul"}, headers=h)
    assert r.status_code == 422
