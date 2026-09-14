"""Schemas do MOD 9 — ParamsCF (parâmetros econômico-financeiros do fluxo de caixa).

Só os parâmetros (TMA, inflação, anos, reajustes) — não é o fluxo de caixa em
si (`CalculadoraCF`, que precisa de TODOS os módulos de investimento pra
calcular algo; ver dominios/financeiro-viabilidade-economica/spec.md). Rodar
o fluxo de caixa de verdade é responsabilidade do módulo `summary`
(orquestração final), não deste endpoint de validação isolada."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ParamsCFPayload(BaseModel):
    taxa_desconto:         float = 0.08
    inflacao:              float = 0.0393
    anos_projeto:          int   = 25
    reajuste_tarifa_ponta: float = 0.010
    reajuste_tarifa_fp:    float = 0.000
    reajuste_demanda_spt:  float = 0.008
    reajuste_combustivel:  float = 0.010


class ParamsCFResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
    taxa_desconto_real: float = 0.0
