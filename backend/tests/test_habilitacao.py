"""Testes da habilitação por prova: criação (admin), tentativa, correção,
concessão de licença, e os casos de segurança/integridade equivalentes aos
que a revisão do app03 pegou (uso único, ownership, validação de entrada)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Exam, ExamAttempt, ModuleLicense, User
from app.habilitacao import service as habilitacao_service
from tests.conftest import auth_headers

EXAM_PAYLOAD = {
    "module": "gridzero",
    "title": "Fundamentos de GridZero",
    "passing_score_pct": 70,
    "questions": [
        {"text": "1 + 1?", "options": ["1", "2", "3"], "correct_index": 1},
        {"text": "Capital do Brasil?", "options": ["SP", "Brasília", "RJ"], "correct_index": 1},
        {"text": "2 + 2?", "options": ["3", "4", "5"], "correct_index": 1},
    ],
}


def _criar_prova(client: TestClient, admin_usuario: User) -> int:
    res = client.post(
        "/habilitacao/admin/provas", json=EXAM_PAYLOAD, headers=auth_headers(admin_usuario)
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ── Autoria (admin) ──────────────────────────────────────────────────────────


def test_no_admin_nao_pode_criar_prova(client: TestClient, usuario: User) -> None:
    res = client.post("/habilitacao/admin/provas", json=EXAM_PAYLOAD, headers=auth_headers(usuario))
    assert res.status_code == 403


def test_admin_cria_prova_com_modulo_invalido_e_rejeitado(
    client: TestClient, admin_usuario: User
) -> None:
    payload = {**EXAM_PAYLOAD, "module": "modulo-que-nao-existe"}
    res = client.post("/habilitacao/admin/provas", json=payload, headers=auth_headers(admin_usuario))
    assert res.status_code == 422


def test_correct_index_fora_do_intervalo_e_rejeitado_antes_de_chegar_no_service(
    client: TestClient, admin_usuario: User
) -> None:
    payload = {
        "module": "gridzero", "title": "x",
        "questions": [{"text": "?", "options": ["a", "b"], "correct_index": 5}],
    }
    res = client.post("/habilitacao/admin/provas", json=payload, headers=auth_headers(admin_usuario))
    assert res.status_code == 422


# ── Fluxo do candidato ───────────────────────────────────────────────────────


def test_prova_aparece_na_listagem_para_quem_nao_tem_o_modulo(
    client: TestClient, admin_usuario: User, usuario: User
) -> None:
    _criar_prova(client, admin_usuario)
    res = client.get("/habilitacao/provas", headers=auth_headers(usuario))
    assert res.status_code == 200
    modulos = [p["module"] for p in res.json()]
    assert "gridzero" in modulos


def test_iniciar_a_mesma_prova_duas_vezes_retorna_a_mesma_tentativa(
    client: TestClient, admin_usuario: User, usuario: User
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    r1 = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario))
    r2 = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario))
    assert r1.json()["attempt_id"] == r2.json()["attempt_id"]


def test_perguntas_nao_expoe_a_resposta_correta(
    client: TestClient, admin_usuario: User, usuario: User
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    res = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario))
    body = res.text
    assert "correct_index" not in body


def test_acertar_o_suficiente_aprova_e_libera_o_modulo(
    client: TestClient, admin_usuario: User, usuario: User, db_session: Session
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()
    perguntas = inicio["questions"]
    # gabarito real: [1, 1, 1] — acerta as 3 (100% >= 70%)
    respostas = {str(p["id"]): 1 for p in perguntas}

    res = client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(usuario),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["passed"] is True
    assert body["modulo_liberado"] is True
    assert body["score_pct"] == 100.0

    lic = db_session.query(ModuleLicense).filter_by(user_id=usuario.id, module="gridzero").one()
    assert lic.enabled is True
    assert lic.source == "exam"


def test_errar_tudo_reprova_e_nao_libera_o_modulo(
    client: TestClient, admin_usuario: User, usuario: User, db_session: Session
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()
    respostas = {str(p["id"]): 0 for p in inicio["questions"]}  # tudo errado

    res = client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(usuario),
    )
    assert res.status_code == 200
    assert res.json()["passed"] is False

    lic = db_session.query(ModuleLicense).filter_by(user_id=usuario.id, module="gridzero").first()
    assert lic is None


def test_prova_ja_aprovada_some_da_listagem(
    client: TestClient, admin_usuario: User, usuario: User
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()
    respostas = {str(p["id"]): 1 for p in inicio["questions"]}
    client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(usuario),
    )
    res = client.get("/habilitacao/provas", headers=auth_headers(usuario))
    assert "gridzero" not in [p["module"] for p in res.json()]


# ── Integridade / segurança ──────────────────────────────────────────────────


def test_submeter_a_mesma_tentativa_duas_vezes_e_rejeitado(
    client: TestClient, admin_usuario: User, usuario: User
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()
    respostas = {str(p["id"]): 1 for p in inicio["questions"]}

    r1 = client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(usuario),
    )
    r2 = client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(usuario),
    )
    assert r1.status_code == 200
    assert r2.status_code == 409


def test_usuario_nao_consegue_submeter_tentativa_de_outro(
    client: TestClient, admin_usuario: User, usuario: User, outro_usuario: User
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()
    respostas = {str(p["id"]): 1 for p in inicio["questions"]}

    res = client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(outro_usuario),
    )
    assert res.status_code == 404


def test_historico_lista_a_tentativa_apos_submissao(
    client: TestClient, admin_usuario: User, usuario: User
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()
    respostas = {str(p["id"]): 1 for p in inicio["questions"]}
    client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(usuario),
    )
    res = client.get("/habilitacao/tentativas/me", headers=auth_headers(usuario))
    assert res.status_code == 200
    hist = res.json()
    assert len(hist) == 1
    assert hist[0]["passed"] is True
    assert hist[0]["module"] == "gridzero"


# ── Regressão dos achados da revisão Codex ──────────────────────────────────


def test_prova_desativada_apos_iniciar_nao_pode_mais_ser_submetida(
    client: TestClient, admin_usuario: User, usuario: User, db_session: Session
) -> None:
    exam_id = _criar_prova(client, admin_usuario)
    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()

    res_desativar = client.patch(
        f"/habilitacao/admin/provas/{exam_id}/ativo",
        json={"is_active": False}, headers=auth_headers(admin_usuario),
    )
    assert res_desativar.status_code == 200

    respostas = {str(p["id"]): 1 for p in inicio["questions"]}  # gabarito certo
    res = client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(usuario),
    )
    assert res.status_code == 409
    assert db_session.query(ModuleLicense).filter_by(user_id=usuario.id, module="gridzero").first() is None


def test_desativar_prova_exatamente_entre_a_checagem_e_o_update_nao_libera_modulo(
    client: TestClient, admin_usuario: User, usuario: User, db_engine, db_session: Session
) -> None:
    """A checagem de is_active em submeter_tentativa lê a prova, decide que
    está ativa, e SÓ DEPOIS chega no UPDATE atômico — se a prova for
    desativada bem nesse intervalo (por outra sessão, como seria numa
    requisição HTTP concorrente de verdade), a leitura antiga não pode valer.

    Tentativa anterior deste teste usava `monkeypatch` na MESMA sessão pra
    simular a corrida — só que isso não provava nada: `expire_on_commit`
    (padrão do SQLAlchemy) expira os objetos da PRÓPRIA sessão que fez o
    commit, então o objeto `exam` já em memória era silenciosamente
    atualizado pra `is_active=False` de qualquer forma, e a checagem
    simples (não a atômica) já pegava o caso — o teste passava mesmo com a
    condição do UPDATE atômico removida de propósito (verificado). Corrigido
    usando duas sessões (identity maps) de fato independentes: uma carrega
    `Exam` primeiro (fica com `is_active=True` em cache, sem ser afetada pelo
    commit de outra sessão), a outra desativa de verdade — reproduz o
    intervalo que a revisão Codex apontou. Nota de precisão: as duas sessões
    compartilham a MESMA conexão física (StaticPool da fixture `db_engine`) —
    o que este teste isola é o cache do identity map (nível ORM), não
    isolamento de conexão de banco; para isso, ver o teste de corrida de
    `iniciar_tentativa` acima, que usa um arquivo sqlite com conexões
    de fato separadas."""
    exam_id = _criar_prova(client, admin_usuario)
    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()
    respostas = {int(k): v for k, v in {str(p["id"]): 1 for p in inicio["questions"]}.items()}

    SessionFactory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    # Sessão do candidato: carrega a prova AGORA (is_active=True) — fica em
    # cache no identity map dela até ELA mesma commitar de novo.
    sessao_candidato = SessionFactory()
    exam_em_cache = sessao_candidato.get(Exam, exam_id)
    assert exam_em_cache.is_active is True
    usuario_na_sessao = sessao_candidato.get(User, usuario.id)

    # "Outra requisição" (admin) desativando de verdade, numa sessão separada.
    sessao_admin = SessionFactory()
    sessao_admin.execute(update(Exam).where(Exam.id == exam_id).values(is_active=False))
    sessao_admin.commit()
    sessao_admin.close()

    # A sessão do candidato ainda vê is_active=True no cache — só o UPDATE
    # atômico (que lê o banco de verdade, não o objeto Python) pode barrar.
    with pytest.raises(HTTPException) as exc_info:
        habilitacao_service.submeter_tentativa(
            sessao_candidato, usuario_na_sessao, inicio["attempt_id"], respostas
        )
    assert exc_info.value.status_code == 409
    sessao_candidato.close()

    assert db_session.query(ModuleLicense).filter_by(user_id=usuario.id, module="gridzero").first() is None


def test_percentual_arredondado_nao_aprova_quem_ficou_abaixo_do_corte_real(
    client: TestClient, admin_usuario: User, usuario: User
) -> None:
    # 17/21 = 80,952...% — arredondado pra 1 casa vira 81,0%, que bateria um
    # corte de 81% mesmo sem o candidato ter alcançado de verdade (achado
    # da revisão Codex). 21 perguntas objetivas de 2 alternativas.
    payload = {
        "module": "gridzero", "title": "Prova de 21 perguntas", "passing_score_pct": 81,
        "questions": [
            {"text": f"q{i}", "options": ["certo", "errado"], "correct_index": 0}
            for i in range(21)
        ],
    }
    res = client.post("/habilitacao/admin/provas", json=payload, headers=auth_headers(admin_usuario))
    exam_id = res.json()["id"]

    inicio = client.post(f"/habilitacao/provas/{exam_id}/iniciar", headers=auth_headers(usuario)).json()
    # acerta exatamente 17 das 21 (as 4 últimas erradas)
    respostas = {
        str(p["id"]): (0 if i < 17 else 1) for i, p in enumerate(inicio["questions"])
    }
    res = client.post(
        f"/habilitacao/tentativas/{inicio['attempt_id']}/submeter",
        json={"respostas": respostas}, headers=auth_headers(usuario),
    )
    body = res.json()
    assert body["score_pct"] == 81.0  # exibição arredondada continua 81,0%...
    assert body["passed"] is False    # ...mas a decisão usa a fração exata (80,95% < 81%)


def test_iniciar_tentativa_sob_corrida_real_nao_duplica_e_nao_quebra() -> None:
    # `:memory:` + StaticPool (fixture padrão) é UMA conexão sqlite crua
    # compartilhada — ótimo pra fixture simples, mas duas threads chamando
    # ao mesmo tempo na mesma conexão corrompem o cursor um do outro
    # (ResourceClosedError, não tem nada a ver com o código sendo testado).
    # Concorrência de verdade precisa de conexões de verdade — um arquivo
    # sqlite temporário, cada thread com sua própria conexão do pool,
    # exatamente como duas requisições HTTP concorrentes teriam no servidor.
    import os
    import tempfile

    from sqlalchemy import create_engine

    from app.db.base import Base

    fd, caminho_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        engine_arquivo = create_engine(f"sqlite:///{caminho_db}")
        Base.metadata.create_all(bind=engine_arquivo)
        SessionFactory = sessionmaker(bind=engine_arquivo, autoflush=False, autocommit=False)

        # Recria prova + usuário nesse banco de arquivo (o exam_id/usuario.id
        # criados via `client`/`db_session` vivem no banco em memória da fixture).
        with SessionFactory() as setup:
            u = User(email="candidato@example.com", name="c", provider="google", provider_sub="s1")
            setup.add(u)
            setup.commit()
            setup.refresh(u)
            user_id_arquivo = u.id

            from app.db.models import Exam, ExamQuestion
            exam = Exam(module="gridzero", title="x", passing_score_pct=70)
            exam.questions = [ExamQuestion(order=0, text="q", options=["a", "b"], correct_index=0)]
            setup.add(exam)
            setup.commit()
            setup.refresh(exam)
            exam_id_arquivo = exam.id

        def _iniciar_em_thread() -> int:
            sessao = SessionFactory()
            try:
                usuario_da_thread = sessao.get(User, user_id_arquivo)
                resultado = habilitacao_service.iniciar_tentativa(sessao, usuario_da_thread, exam_id_arquivo)
                return resultado.attempt_id
            finally:
                sessao.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(_iniciar_em_thread)
            f2 = pool.submit(_iniciar_em_thread)
            ids = {f1.result(), f2.result()}

        assert len(ids) == 1, f"duas tentativas abertas criadas em vez de uma: {ids}"

        with SessionFactory() as verificacao:
            abertas = (
                verificacao.query(ExamAttempt)
                .filter_by(user_id=user_id_arquivo, exam_id=exam_id_arquivo, submitted_at=None)
                .count()
            )
            assert abertas == 1
    finally:
        os.remove(caminho_db)
