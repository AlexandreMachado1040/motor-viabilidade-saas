"""Regras de negócio da habilitação por prova.

Aprovar uma prova (score >= passing_score_pct) concede a ModuleLicense do
módulo correspondente com source='exam' — reaproveita o mecanismo de licença
já existente (admin/service.py#definir_modulos usa o mesmo ModuleLicense com
source='manual'), não inventa um caminho de acesso paralelo.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import MODULOS, Exam, ExamAttempt, ExamQuestion, ModuleLicense, User
from .schemas import (
    ExamAdminView, ExamAttemptHistorico, ExamAttemptResultado, ExamAttemptStarted,
    ExamCreate, ExamPublic, ExamQuestionPublic,
)

# ── Mapeamento ORM → schema (mesmo padrão de admin/service.py#_para_admin_user) ─


def _to_exam_public(exam: Exam) -> ExamPublic:
    return ExamPublic(
        id=exam.id, module=exam.module, title=exam.title,
        passing_score_pct=exam.passing_score_pct,
        time_limit_minutes=exam.time_limit_minutes,
        num_questions=len(exam.questions),
    )


def _to_admin_view(exam: Exam) -> ExamAdminView:
    return ExamAdminView(
        id=exam.id, module=exam.module, title=exam.title,
        passing_score_pct=exam.passing_score_pct,
        time_limit_minutes=exam.time_limit_minutes,
        is_active=exam.is_active, num_questions=len(exam.questions),
    )


def _to_attempt_started(tentativa: ExamAttempt, exam: Exam) -> ExamAttemptStarted:
    return ExamAttemptStarted(
        attempt_id=tentativa.id,
        exam=_to_exam_public(exam),
        questions=[
            ExamQuestionPublic(id=q.id, order=q.order, text=q.text, options=q.options)
            for q in exam.questions
        ],
        started_at=tentativa.started_at,
    )


def _to_attempt_resultado(tentativa: ExamAttempt, exam: Exam) -> ExamAttemptResultado:
    return ExamAttemptResultado(
        attempt_id=tentativa.id, module=exam.module,
        score_pct=tentativa.score_pct or 0.0,
        passing_score_pct=exam.passing_score_pct,
        passed=bool(tentativa.passed),
        modulo_liberado=bool(tentativa.passed),
    )


def _to_attempt_historico(tentativa: ExamAttempt) -> ExamAttemptHistorico:
    return ExamAttemptHistorico(
        attempt_id=tentativa.id, exam_id=tentativa.exam_id,
        module=tentativa.exam.module, exam_title=tentativa.exam.title,
        started_at=tentativa.started_at, submitted_at=tentativa.submitted_at,
        score_pct=tentativa.score_pct, passed=tentativa.passed,
    )


# ── Candidato ────────────────────────────────────────────────────────────────


def listar_provas_disponiveis(db: Session, user: User) -> list[ExamPublic]:
    """Provas ativas para módulos que o usuário ainda não tem — não faz
    sentido oferecer prova de recertificação nesta versão (ver spec.md,
    'expiração e recertificação' fica pra depois)."""
    ativos = user.modulos_ativos
    provas = db.scalars(
        select(Exam).where(Exam.is_active.is_(True)).order_by(Exam.module)
    ).all()
    return [_to_exam_public(p) for p in provas if p.module not in ativos]


def obter_prova_ativa(db: Session, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None or not exam.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prova não encontrada.")
    return exam


def _tentativa_pendente(db: Session, user_id: int, exam_id: int) -> ExamAttempt | None:
    return db.scalar(
        select(ExamAttempt).where(
            ExamAttempt.user_id == user_id,
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.submitted_at.is_(None),
        )
    )


def iniciar_tentativa(db: Session, user: User, exam_id: int) -> ExamAttemptStarted:
    exam = obter_prova_ativa(db, exam_id)

    # Retoma uma tentativa em andamento em vez de criar outra — evita lixo de
    # tentativas abertas se o candidato recarregar a página.
    pendente = _tentativa_pendente(db, user.id, exam_id)
    if pendente is not None:
        return _to_attempt_started(pendente, exam)

    # Entre o SELECT acima e este INSERT, outra requisição concorrente do
    # mesmo usuário pode ter criado a tentativa primeiro — o índice único
    # parcial em ExamAttempt (`uq_exam_attempts_aberta_por_usuario`) é quem
    # garante isso de verdade; aqui só tratamos a violação graciosamente em
    # vez de devolver 500 (achado de segurança, revisão Codex, reproduzido
    # com 2 conexões concorrentes antes do índice existir).
    tentativa = ExamAttempt(user_id=user.id, exam_id=exam_id)
    db.add(tentativa)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        pendente = _tentativa_pendente(db, user.id, exam_id)
        if pendente is None:
            raise  # não foi essa a causa do conflito — deixa o erro real subir
        return _to_attempt_started(pendente, exam)
    db.refresh(tentativa)
    return _to_attempt_started(tentativa, exam)


def obter_tentativa_do_usuario(db: Session, user: User, attempt_id: int) -> ExamAttempt:
    tentativa = db.get(ExamAttempt, attempt_id)
    if tentativa is None or tentativa.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tentativa não encontrada.")
    return tentativa


def _conceder_licenca_por_prova(db: Session, user_id: int, module: str) -> None:
    lic = db.scalar(
        select(ModuleLicense).where(
            ModuleLicense.user_id == user_id, ModuleLicense.module == module
        )
    )
    if lic is None:
        db.add(ModuleLicense(user_id=user_id, module=module, enabled=True, source="exam"))
    else:
        lic.enabled = True
        lic.source = "exam"
        lic.granted_at = func.now()


def submeter_tentativa(
    db: Session, user: User, attempt_id: int, respostas: dict[int, int]
) -> ExamAttemptResultado:
    tentativa = obter_tentativa_do_usuario(db, user, attempt_id)
    if tentativa.submitted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tentativa já foi submetida.")

    exam = db.get(Exam, tentativa.exam_id)
    if exam is None or not exam.is_active:
        # Achado de segurança (revisão Codex): uma tentativa aberta antes de
        # a prova ser desativada continuava aprovável depois — a prova pode
        # ter sido desativada justamente por estar comprometida (gabarito
        # vazado, pergunta errada). Tentativa em aberto não é mais aceita.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta prova não está mais disponível. A tentativa foi invalidada.",
        )

    perguntas: dict[int, ExamQuestion] = {q.id: q for q in exam.questions}
    total = len(perguntas)
    acertos = sum(
        1 for qid, resp in respostas.items()
        if qid in perguntas and perguntas[qid].correct_index == resp
    )
    score_pct = round(100 * acertos / total, 1) if total else 0.0
    # Decide com a fração exata (acertos*100 >= corte*total), não com o
    # percentual já arredondado — achado de segurança (revisão Codex):
    # arredondar antes de comparar contra um corte inteiro pode aprovar quem
    # não atingiu o corte de verdade (ex.: 17/21 = 80,95% arredonda pra 81,0%
    # e passaria um corte de 81%, mesmo sendo genuinamente menor).
    passou = (100 * acertos) >= (exam.passing_score_pct * total) if total else False

    # Atômico: só marca como submetida se (a) ainda estiver em aberto e (b) a
    # prova continuar ativa NO INSTANTE do UPDATE — decide por `rowcount`, não
    # por SELECTs anteriores. A checagem de `is_active` acima (linha ~162) é
    # só a mensagem de erro mais cedo/específica pro caso comum; quem decide
    # de verdade é a condição `exam_id IN (...)` aqui dentro, porque a prova
    # pode ser desativada bem no intervalo entre aquele SELECT e este UPDATE
    # (achado de segurança, revisão Codex, reproduzido com 2 conexões
    # pausando exatamente nesse intervalo). Mesmo padrão de
    # app03/apps/workers/api/src/lib/db.ts#definirSenhaComConvite.
    resultado = db.execute(
        update(ExamAttempt)
        .where(
            ExamAttempt.id == attempt_id,
            ExamAttempt.submitted_at.is_(None),
            ExamAttempt.exam_id.in_(select(Exam.id).where(Exam.is_active.is_(True))),
        )
        .values(
            submitted_at=func.now(),
            answers={str(k): v for k, v in respostas.items()},
            score_pct=score_pct,
            passed=passou,
        )
    )
    if resultado.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Tentativa já foi submetida ou a prova não está mais disponível.",
        )

    if passou:
        _conceder_licenca_por_prova(db, user.id, exam.module)

    db.commit()
    db.refresh(tentativa)
    return _to_attempt_resultado(tentativa, exam)


def historico_tentativas(db: Session, user: User) -> list[ExamAttemptHistorico]:
    tentativas = db.scalars(
        select(ExamAttempt)
        .where(ExamAttempt.user_id == user.id)
        .order_by(ExamAttempt.started_at.desc())
    ).all()
    return [_to_attempt_historico(t) for t in tentativas]


# ── Admin: autoria de provas ─────────────────────────────────────────────────


def criar_prova(db: Session, payload: ExamCreate) -> ExamAdminView:
    if payload.module not in MODULOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Módulo inválido: '{payload.module}'. Válidos: {MODULOS}.",
        )
    exam = Exam(
        module=payload.module,
        title=payload.title,
        passing_score_pct=payload.passing_score_pct,
        time_limit_minutes=payload.time_limit_minutes,
    )
    exam.questions = [
        ExamQuestion(
            order=i, text=q.text, options=q.options, correct_index=q.correct_index
        )
        for i, q in enumerate(payload.questions)
    ]
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _to_admin_view(exam)


def listar_provas_admin(db: Session) -> list[ExamAdminView]:
    provas = db.scalars(select(Exam).order_by(Exam.module)).all()
    return [_to_admin_view(p) for p in provas]


def _obter_prova_orm(db: Session, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prova não encontrada.")
    return exam


def definir_prova_ativa(db: Session, exam_id: int, ativo: bool) -> ExamAdminView:
    exam = _obter_prova_orm(db, exam_id)
    exam.is_active = ativo
    db.commit()
    db.refresh(exam)
    return _to_admin_view(exam)
