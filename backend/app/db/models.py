"""Modelos ORM: usuário e licenças de módulo (espelham motor_viabilidade.LicencaModulos)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    TypeDecorator, UniqueConstraint, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import Base

# Módulos licenciáveis — mesmas chaves de motor_viabilidade.LicencaModulos.
# Por padrão liberamos os módulos básicos (espelha os defaults da dataclass).
MODULOS = [
    "load", "grid", "solar", "bess_ponta", "gen_ponta", "gen_form",
    "bess_form", "new_grid", "cf", "summary", "gridzero",
]
MODULOS_PADRAO = {"load", "grid", "cf", "summary"}


class UTCDateTime(TypeDecorator):
    """`DateTime(timezone=True)` que normaliza qualquer valor aware pra UTC
    ANTES de virar parâmetro do bind, não só na leitura.

    Existe porque SQLite (via SQLAlchemy) grava o valor de PAREDE de um
    datetime aware tal como veio, sem convertê-lo pra UTC primeiro, e sempre
    relê naive depois — sem essa normalização, um valor aware em fuso
    diferente de UTC (ex.: +03:00) fica com a hora errada pra sempre, e não
    tem correção possível na hora de comparar (o dado certo já foi perdido na
    gravação; achado de segurança, revisão Codex).

    Um `@validates` no atributo do ORM (ver `ModuleLicense`) resolve a
    atribuição direta (`lic.expires_at = valor`) e ainda ajuda o caso de
    comparar um valor ainda em memória, antes do primeiro flush — mas não
    dispara pra um `UPDATE`/`INSERT` via SQLAlchemy Core (`update(...).values(...)`),
    que vai direto pro bind sem passar pelo atributo instrumentado (achado de
    segurança, revisão Codex, reproduzido: um Core `update` com offset não-UTC
    persistia a hora errada mesmo com o `@validates` no lugar). Este
    TypeDecorator cobre os dois caminhos (ORM e Core), porque
    `process_bind_param` roda pra qualquer parâmetro tipado como esta coluna —
    **não** cobre SQL textual cru sem bind tipado (`text("UPDATE ... :x")` sem
    passar pelo `Column`/`mapped_column`) nem escrita fora do SQLAlchemy (outro
    processo gravando direto no arquivo SQLite); nenhum dos dois é usado hoje
    pra `expires_at`, mas vale saber o limite real da garantia. Testado contra
    SQLite (achado original); descartar `tzinfo` incondicionalmente após
    `astimezone(utc)` não deve ser presumido portável pra outro banco sem
    verificar o dialeto correspondente."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, dialect) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(dt.timezone.utc)
        return value.replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True)
    email:        Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name:         Mapped[str | None] = mapped_column(String(255))
    picture:      Mapped[str | None] = mapped_column(String(1024))
    provider:     Mapped[str] = mapped_column(String(32))          # google | microsoft
    provider_sub: Mapped[str] = mapped_column(String(255), index=True)
    is_active:    Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin:     Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:   Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at:   Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    licenses: Mapped[list["ModuleLicense"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin")

    @property
    def modulos_ativos(self) -> set[str]:
        """Módulos com licença habilitada E ainda dentro da validade.

        Ponto único de verdade sobre "o que o usuário pode usar agora" —
        `/me`, o painel admin, a ponte pro motor (`licenca/service.py`) e
        `require_module()` leem todos daqui, então a expiração (achado de
        auditoria, ver dominios/licenciamento-habilitacao/spec.md) fica
        garantida em todo lugar de uma vez, sem duplicar a checagem em cada
        consumidor. A comparação em si mora em `ModuleLicense.expirada()` —
        ver lá o porquê de não dar pra só comparar `expires_at` direto."""
        return {
            lic.module for lic in self.licenses
            if lic.enabled and not lic.expirada()
        }


class ModuleLicense(Base):
    __tablename__ = "module_licenses"
    __table_args__ = (UniqueConstraint("user_id", "module", name="uq_user_module"),)

    id:      Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module:  Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 'manual' (admin liberou direto) | 'exam' (aprovado numa prova de habilitação).
    # Default 'manual' preserva o significado de toda licença já existente.
    source:  Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")
    granted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    # NULL = sem validade definida (comportamento de sempre, preservado pra
    # toda licença já existente e pra concessão manual/por prova até que haja
    # uma decisão de produto sobre prazo de recertificação — ver
    # dominios/licenciamento-habilitacao/spec.md, "expiração e recertificação
    # fica pra depois"). Quando setado, `modulos_ativos` para de contar o
    # módulo assim que `expires_at` for ultrapassado — não é preciso revogar
    # (`enabled=False`) manualmente.
    expires_at: Mapped[dt.datetime | None] = mapped_column(
        UTCDateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="licenses")

    @staticmethod
    def _utc_naive(valor: dt.datetime) -> dt.datetime:
        """Normaliza pra UTC naive — não basta descartar `tzinfo` de quem já
        tem um: um valor aware em outro fuso (ex.: +03:00) tem uma hora de
        parede diferente da hora UTC equivalente. `.replace(tzinfo=None)`
        sozinho manteria a hora de parede errada. `astimezone(utc)` primeiro
        corrige isso; só então o `tzinfo` pode ser descartado com segurança.
        Valores já naive (o caso normal, vindos do próprio SQLite) são
        tratados como já estando em UTC."""
        if valor.tzinfo is not None:
            valor = valor.astimezone(dt.timezone.utc)
        return valor.replace(tzinfo=None)

    @validates("expires_at")
    def _normalizar_expires_at(self, key: str, valor: dt.datetime | None) -> dt.datetime | None:
        """Normaliza já na atribuição (não só no bind do `UTCDateTime`,
        embora esse já bastasse pra corrigir o que é persistido): sem isso,
        um valor aware fica aware em memória até o próximo flush, e comparar
        contra um "agora" naive nesse intervalo (ex.: `modulos_ativos` logo
        depois de montar o objeto, antes de qualquer commit) levantaria
        `TypeError`. `UTCDateTime.process_bind_param` é quem garante que
        QUALQUER escrita — inclusive um `UPDATE`/`INSERT` via SQLAlchemy Core,
        que não passa pelo atributo instrumentado e portanto não aciona este
        `@validates` — persiste em UTC corretamente; ver o docstring de
        `UTCDateTime` pra esse achado."""
        return self._utc_naive(valor) if valor is not None else None

    def expirada(self, agora: dt.datetime | None = None) -> bool:
        """`agora` aceita naive (assumido UTC) ou aware (qualquer fuso) —
        normalizado do mesmo jeito que `expires_at`, então comparar os dois
        nunca levanta `TypeError` por misturar aware/naive. `self.expires_at`
        já chega aqui normalizado (via `@validates` ou via `UTCDateTime` no
        bind, dependendo de como foi escrito) — chamar `_utc_naive` de novo
        aqui é só defesa em profundidade, não o que resolve o achado do offset
        não-UTC (isso já foi resolvido antes de chegar aqui)."""
        if self.expires_at is None:
            return False
        limite = self._utc_naive(self.expires_at)
        referencia = self._utc_naive(agora if agora is not None else dt.datetime.now(dt.timezone.utc))
        return limite <= referencia


# ── Habilitação por prova ──────────────────────────────────────────────────
# Um Exam é vinculado a um módulo de MODULOS; aprovar (score >= passing_score_pct)
# concede a ModuleLicense correspondente com source='exam' — sem inventar um
# mecanismo de licença paralelo (ver dominios/licenciamento-habilitacao/spec.md).

class Exam(Base):
    __tablename__ = "exams"

    id:                 Mapped[int] = mapped_column(Integer, primary_key=True)
    module:             Mapped[str] = mapped_column(String(32), index=True)
    title:              Mapped[str] = mapped_column(String(255))
    passing_score_pct:  Mapped[int] = mapped_column(Integer, default=70)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active:          Mapped[bool] = mapped_column(Boolean, default=True)
    created_at:         Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    questions: Mapped[list["ExamQuestion"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan",
        order_by="ExamQuestion.order", lazy="selectin")


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id:            Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id:       Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    order:         Mapped[int] = mapped_column(Integer, default=0)
    text:          Mapped[str] = mapped_column(Text)
    options:       Mapped[list[str]] = mapped_column(JSON)
    # Índice (em `options`) da alternativa correta — nunca deve ir pro cliente
    # antes da correção (ver ExamQuestionPublic em habilitacao/schemas.py).
    correct_index: Mapped[int] = mapped_column(Integer)

    exam: Mapped["Exam"] = relationship(back_populates="questions")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (
        # Só uma tentativa em aberto por usuário×prova — sem isso, duas
        # requisições de "iniciar" concorrentes (SELECT não achou nenhuma
        # pendente, então as duas inserem) criavam duplicatas (achado de
        # segurança, revisão Codex, reproduzido com 2 conexões concorrentes).
        # Índice parcial: só entram no UNIQUE as linhas ainda não submetidas.
        Index(
            "uq_exam_attempts_aberta_por_usuario",
            "user_id", "exam_id", unique=True,
            sqlite_where=text("submitted_at IS NULL"),
        ),
    )

    id:           Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id:      Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exam_id:      Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    started_at:   Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    # NULL enquanto em andamento — é o que garante uso único (ver
    # habilitacao/service.py#submeter_tentativa: UPDATE condicionado a
    # submitted_at IS NULL, checando rowcount, não SELECT-depois-UPDATE).
    submitted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answers:      Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    score_pct:    Mapped[float | None] = mapped_column(Float, nullable=True)
    passed:       Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    user: Mapped["User"] = relationship(lazy="selectin")
    exam: Mapped["Exam"] = relationship(lazy="selectin")
