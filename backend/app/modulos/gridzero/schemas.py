"""Schemas do MOD 11 — InputGridZero (sistema fotovoltaico sem injeção na rede).

Diferente dos MOD 3-9: `InputGridZero` TEM `.validar()` no motor (4 asserts:
demanda_horaria_kw e perfil_solar_norm com 24 valores, potencia_ac_kw e
capex_kwp positivos) e `CalculadoraGridZero.calcular()` já devolve um
resultado financeiro completo e autocontido (VPL, payback descontado,
autoconsumo, simultaneidade) — não precisa de nenhum outro módulo, ao
contrário de bess_ponta/solar (que dependiam de `grid`). Por isso o
`/validar` aqui roda o cálculo de verdade, não só ecoa um derivado simples.

`AnaliseComparativaGridZero` (compara 5 tamanhos de sistema de uma vez, ver
motor) fica de fora — é uma feature mais rica (múltiplos cenários) que o
padrão de "1 payload → 1 resumo" dos outros módulos; pode virar uma rota
`/comparar` própria depois, se fizer sentido de produto."""
from __future__ import annotations

from pydantic import BaseModel, Field

# Mesmos defaults de motor_viabilidade.InputGridZero — dados de demanda
# horária média diária e perfil solar normalizado (Campinas/SP) extraídos da
# planilha de referência do artigo Canal Solar N°33.
_DEMANDA_HORARIA_PADRAO = [
    53.3, 52.1, 52.3, 51.8, 51.1, 51.2,
    51.5, 62.5, 73.0, 77.5, 77.3, 77.4,
    79.8, 80.3, 79.4, 78.1, 78.8, 77.2,
    66.8, 67.4, 73.1, 73.4, 63.9, 54.3,
]
_PERFIL_SOLAR_NORM_PADRAO = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.004,
    0.160, 0.410, 0.630, 0.720, 0.740, 0.750,
    0.740, 0.700, 0.620, 0.490, 0.330, 0.090,
    0.002, 0.000, 0.000, 0.000, 0.000, 0.000,
]


class InputGridZeroPayload(BaseModel):
    potencia_ac_kw:        float = 75.0
    sobredimensionamento:  float = 1.32
    performance_ratio:     float = 0.78
    preset_concessionaria: str   = "cpfl_b3"
    te_kwh:                float = 0.287
    tusd_kwh:              float = 0.388
    icms_pct:              float = 18.0
    piscofins_pct:         float = 5.0
    reajuste_tarifa_pct:   float = 5.0
    capex_kwp:             float = 3000.0
    om_pct_capex:          float = 1.0
    ipca_pct:              float = 4.5
    tma_pct:               float = 12.0
    anos_projeto:          int   = 25
    demanda_horaria_kw: list[float] = Field(
        default_factory=lambda: list(_DEMANDA_HORARIA_PADRAO),
        description="24 valores (kW médio por hora do dia).",
    )
    perfil_solar_norm: list[float] = Field(
        default_factory=lambda: list(_PERFIL_SOLAR_NORM_PADRAO),
        description="24 valores (fração de pico, 0-1).",
    )


class GridZeroResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)

    potencia_ac_kw:  float = 0.0
    potencia_cc_kwp: float = 0.0
    capex_total_r:   float = 0.0

    autoconsumo_kwh_dia:   float = 0.0
    geracao_gz_kwh_dia:    float = 0.0
    consumo_total_kwh_dia: float = 0.0
    excedente_kwh_dia:     float = 0.0
    autoconsumo_pct:       float = 0.0
    simultaneidade_pct:    float = 0.0
    autoconsumo_anual_kwh: float = 0.0
    geracao_anual_kwh:     float = 0.0
    consumo_anual_kwh:     float = 0.0

    saving_ano1_r: float = 0.0
    payback_anos:  float | None = None
    vpl_r:         float = 0.0
    vpl_kwp_r:     float = 0.0
    tma_pct:       float = 12.0
    tarifa_kwh:    float = 0.0

    fc_nominal:   list[float] = Field(default_factory=list)
    fc_acumulado: list[float] = Field(default_factory=list)
