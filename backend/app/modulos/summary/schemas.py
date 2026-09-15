"""Schemas do MOD 10 — Summary (orquestração final do estudo de viabilidade).

Diferente dos MOD 1-9/11: não existe `InputSummary` no motor — `summary` é
`EstudoViabilidade.gerar_summary()`, que agrega o que já foi carregado nos
outros módulos + o fluxo de caixa consolidado (`calcular_cf()`). O payload
aqui por isso é composto pelos schemas dos módulos já construídos (load e
grid obrigatórios — são a base de qualquer estudo, mesma ordem "1.load →
2.grid → ... → 9.cf → 10.summary" documentada no motor; os demais são
opcionais, só entram no fluxo de caixa se enviados)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..bess_form.schemas import InputBESSFormadorPayload
from ..bess_ponta.schemas import InputBESSPontaPayload
from ..cf.schemas import ParamsCFPayload
from ..gen_form.schemas import InputGeradorFormadorPayload
from ..gen_ponta.schemas import InputGeradorPontaPayload
from ..grid.schemas import InputGridPayload
from ..grid.tarifas_schemas import SimuladorTarifasPayload
from ..load.schemas import InputLoadPayload
from ..new_grid.schemas import InputNewGridPayload
from ..solar.schemas import InputSolarSCDEEPayload


class SummaryPayload(BaseModel):
    load: InputLoadPayload
    grid: InputGridPayload
    params_cf: ParamsCFPayload = Field(default_factory=ParamsCFPayload)

    # Fatura do simulador de tarifas (MOD 2), opcional: quando enviada, a
    # modalidade escolhida vira o baseline da rede e as tarifas de consumo
    # usadas pelos investimentos (EstudoViabilidade.carregar_fatura_grid).
    tarifas:    SimuladorTarifasPayload | None = None
    modalidade: Literal["convencional", "azul", "verde", "baixa_tensao"] | None = None

    # Módulos de investimento — opcionais, só entram no fluxo de caixa
    # consolidado (VPL/TIR/payback) se enviados. `None` = módulo não
    # contratado/não incluído neste estudo (mesmo critério de
    # LicencaModulos: flag False = módulo fora).
    solar:      InputSolarSCDEEPayload | None = None
    bess_ponta: InputBESSPontaPayload | None = None
    gen_ponta:  InputGeradorPontaPayload | None = None
    gen_form:   InputGeradorFormadorPayload | None = None
    bess_form:  InputBESSFormadorPayload | None = None
    new_grid:   InputNewGridPayload | None = None

    @model_validator(mode="after")
    def _tarifas_com_modalidade(self) -> "SummaryPayload":
        if (self.tarifas is None) != (self.modalidade is None):
            raise ValueError("tarifas e modalidade devem ser enviadas juntas.")
        return self


class ProjetoResumo(BaseModel):
    concessionaria:     str | None = None
    subgrupo:           str | None = None
    modalidade:         str | None = None
    fonte_tarifas:      Literal["grid", "simulador"] | None = None
    demanda_maxima_kw:  float | None = None
    potencia_solar_kwp: float | None = None
    energia_bess_kwh:   float | None = None


class CustosResumo(BaseModel):
    opex_grid_anual: float | None = None
    capex_total:     float | None = None


class IndicadoresResumo(BaseModel):
    vpl:     float | None = None
    tir_pct: float | None = None
    payback: int | None = None
    roi:     float | None = None
    viavel:  bool | None = None


class ModulosAtivos(BaseModel):
    load: bool = False
    grid: bool = False
    solar: bool = False
    bess_ponta: bool = False
    gen_ponta: bool = False
    gen_form: bool = False
    bess_form: bool = False
    new_grid: bool = False
    cf: bool = False
    summary: bool = False
    gridzero: bool = False


class SummaryResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
    projeto:      ProjetoResumo = Field(default_factory=ProjetoResumo)
    custos:       CustosResumo = Field(default_factory=CustosResumo)
    indicadores:  IndicadoresResumo = Field(default_factory=IndicadoresResumo)
    modulos_ativos: ModulosAtivos = Field(default_factory=ModulosAtivos)
