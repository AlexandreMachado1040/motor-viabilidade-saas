"""MOD 2 — Tarifas e encargos da concessionária (+ ingestão da API ANEEL)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InputGrid:
    """Módulo 2 — Tarifas e encargos da concessionária."""
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

    @property
    def tarifa_ponta(self) -> float:
        return self.tusd_ponta + self.te_ponta

    @property
    def tarifa_fp(self) -> float:
        return self.tusd_fp + self.te_fp

    @classmethod
    def de_api_aneel(cls, dados_api: dict) -> "InputGrid":
        g = cls()
        mapa = {
            "csi_tusd_ponta": "tusd_ponta", "csi_tusd_fp": "tusd_fp",
            "csi_te_ponta": "te_ponta",     "csi_te_fp": "te_fp",
            "csi_demanda_sem_posto": "demanda_sem_posto",
            "csi_demanda_geracao": "demanda_geracao",
            "csi_tusd_fio_a_p": "tusd_fio_a_p",
            "csi_tusd_fio_b_p": "tusd_fio_b_p",
            "csi_fator_k": "fator_k",
            "csi_outros_p": "outros_p",
            "csi_outros_fp": "outros_fp",
        }
        for api_key, attr in mapa.items():
            if api_key in dados_api and dados_api[api_key] is not None:
                setattr(g, attr, float(dados_api[api_key]))
        return g


__all__ = ["InputGrid"]
