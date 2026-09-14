"""Schemas da habilitação por prova: provas, tentativas e autoria (admin)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


# ── Candidato ────────────────────────────────────────────────────────────────

class ExamPublic(BaseModel):
    """Prova disponível — resumo pra listagem, sem perguntas."""
    id: int
    module: str
    title: str
    passing_score_pct: int
    time_limit_minutes: int | None
    num_questions: int


class ExamQuestionPublic(BaseModel):
    """Pergunta sem a resposta correta — o único formato que vai ao candidato
    antes da correção."""
    id: int
    order: int
    text: str
    options: list[str]


class ExamAttemptStarted(BaseModel):
    attempt_id: int
    exam: ExamPublic
    questions: list[ExamQuestionPublic]
    started_at: datetime


class SubmeterTentativaRequest(BaseModel):
    respostas: dict[int, int] = Field(
        description="Mapa {id_da_pergunta: índice da alternativa escolhida}."
    )


class ExamAttemptResultado(BaseModel):
    attempt_id: int
    module: str
    score_pct: float
    passing_score_pct: int
    passed: bool
    modulo_liberado: bool


class ExamAttemptHistorico(BaseModel):
    attempt_id: int
    exam_id: int
    module: str
    exam_title: str
    started_at: datetime
    submitted_at: datetime | None
    score_pct: float | None
    passed: bool | None


# ── Admin: autoria de provas ─────────────────────────────────────────────────

class ExamQuestionIn(BaseModel):
    text: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=10)
    correct_index: int = Field(ge=0)

    @model_validator(mode="after")
    def _correct_index_dentro_do_intervalo(self) -> "ExamQuestionIn":
        if self.correct_index >= len(self.options):
            raise ValueError(
                f"correct_index ({self.correct_index}) fora do intervalo de "
                f"options (0..{len(self.options) - 1})."
            )
        return self


class ExamCreate(BaseModel):
    module: str
    title: str = Field(min_length=1)
    passing_score_pct: int = Field(default=70, ge=1, le=100)
    time_limit_minutes: int | None = Field(default=None, ge=1)
    questions: list[ExamQuestionIn] = Field(min_length=1)


class ExamAdminView(BaseModel):
    id: int
    module: str
    title: str
    passing_score_pct: int
    time_limit_minutes: int | None
    is_active: bool
    num_questions: int


class SetExamAtivoRequest(BaseModel):
    is_active: bool
