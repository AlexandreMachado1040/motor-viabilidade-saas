"""Schemas do MOD 3 — InputSolarSCDEE (sistema solar GD/compensação + solarimetria).

`calcular_opex_energia_mensal`/`calcular_opex_demanda_mensal` do motor não
entram aqui — precisam de `InputGrid` (outro módulo), fora do escopo de
validar um módulo isolado (mesmo critério de InputBESSPonta)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class InputSolarSCDEEPayload(BaseModel):
    estado:                 str   = "São Paulo"
    potencia_ca_kw:         float = 211.27
    potencia_cc_kwp:        float = 300.0
    sobrecarga_inversor:    float = 1.42
    capex_r:                float = 885000.0
    om_anual_r:             float = 1500.0
    degradacao_ano1:        float = 0.02
    degradacao_demais:      float = 0.0055
    custo_troca_inversor_r: float = 50000.0
    ano_troca_inversor:     int   = 12
    modalidade_gd:          str   = "GDIII"
    data_estudo_ano:        int   = 2024
    cronograma_transicao: dict[int, float] = Field(default_factory=lambda: {
        2023: 0.15, 2024: 0.30, 2025: 0.45, 2026: 0.60, 2027: 0.75, 2028: 0.90,
    })
    tusd_ponta:           float = 1.326
    tusd_fp:              float = 0.118
    te_ponta:             float = 0.379
    te_fp:                float = 0.232
    tusd_fio_a_p:         float = 0.25728
    tusd_fio_b_p:         float = 1.130074
    outros_p:             float = 0.305195
    demanda_geracao_r:    float = 9.45
    potencia_gerada_kw:   list[list[float]] = Field(
        default_factory=list, description="12 meses × 24 horas, kW médio por hora."
    )
    potencia_injetada_kw: list[list[float]] = Field(
        default_factory=list, description="12 meses × 24 horas, kW médio por hora (negativo = injeção)."
    )
    fonte_dados: str = "manual"
    dados_sonda: dict = Field(default_factory=dict)
    dados_pvgis: dict = Field(default_factory=dict)
    dados_tmy:   dict = Field(default_factory=dict)


class SolarSCDEEResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
    periodo_transicao_vigente: float = 0.0
    energia_gerada_mensal_kwh: list[float] = Field(default_factory=list)
    energia_injetada_mensal_kwh: list[float] = Field(default_factory=list)
