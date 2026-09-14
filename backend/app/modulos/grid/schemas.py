"""Schemas do MOD 2 — InputGrid (tarifas e encargos da concessionária).

Campos e defaults espelham motor_viabilidade.InputGrid — mesmo dataclass
plano (nenhum campo aninhado), mesmos valores-padrão (dados de referência da
planilha original, concessionária Cemig-D)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class InputGridPayload(BaseModel):
    concessionaria:        str   = "Cemig-D"
    ano_revisao:           int   = 2023
    subgrupo:              str   = "A4"
    modalidade:            str   = "Verde"
    tusd_ponta:            float = 1.326
    tusd_fp:               float = 0.118
    te_ponta:              float = 0.379
    te_fp:                 float = 0.232
    tusd_fio_a_p:          float = 0.25728
    tusd_fio_b_p:          float = 1.130074
    tusd_tfsee_p:          float = 0.000341
    tusd_pd_p:             float = 0.0093775
    te_pd_p:               float = 0.0027280
    outros_p:              float = 0.305195
    tusd_fio_a_fp:         float = 0.0
    tusd_fio_b_fp:         float = 0.0
    tusd_tfsee_fp:         float = 0.00042
    tusd_pd_fp:            float = 0.00042
    te_pd_fp:              float = 0.0028
    outros_fp:             float = 0.34640
    demanda_sem_posto:     float = 16.54
    tusd_fio_a_dem:        float = 5.544208
    tusd_fio_b_dem:        float = 13.513180
    outros_dem:            float = -2.520696
    demanda_geracao:       float = 9.45
    fator_k:               float = 4.8714
    demanda_contratada_kw: float = 250.488


class GridResumo(BaseModel):
    """Resultado da validação + derivados do InputGrid."""
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
    tarifa_ponta: float = 0.0   # tusd_ponta + te_ponta (R$/kWh)
    tarifa_fp: float = 0.0      # tusd_fp + te_fp (R$/kWh)
