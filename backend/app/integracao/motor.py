"""
Ponte de importação para o pacote ``motor_viabilidade`` (que vive em ``src/``).

Garante que ``<repo>/src`` esteja no ``sys.path`` para que o backend reutilize as
classes do motor sem precisar instalar o pacote nem depender de PYTHONPATH.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Optional


def _garantir_src_no_path() -> None:
    # backend/app/integracao/motor.py → parents[3] = raiz do repo (yuriNEW)
    raiz = pathlib.Path(__file__).resolve().parents[3]
    src = raiz / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


_garantir_src_no_path()


def get_input_load_cls() -> Optional[type]:
    """Retorna a classe motor_viabilidade.InputLoad, ou None se indisponível."""
    try:
        from motor_viabilidade import InputLoad
        return InputLoad
    except Exception:
        return None


def exemplo_load_payload() -> Optional[dict[str, Any]]:
    """Dados de carga da planilha original (para pré-preencher o formulário)."""
    try:
        from motor_viabilidade.exemplos import exemplo_planilha_original
        load = exemplo_planilha_original().load
        if load is None:
            return None
        return {
            "demanda_maxima_kw": load.demanda_maxima_kw,
            "demanda_kw": load.demanda_kw,
            "energia_ponta_kwh": load.energia_ponta_kwh,
            "energia_fp_kwh": load.energia_fp_kwh,
        }
    except Exception:
        return None


def get_input_grid_cls() -> Optional[type]:
    """Retorna a classe motor_viabilidade.InputGrid, ou None se indisponível."""
    try:
        from motor_viabilidade import InputGrid
        return InputGrid
    except Exception:
        return None


def exemplo_grid_payload() -> Optional[dict[str, Any]]:
    """Tarifas/encargos da planilha original (para pré-preencher o formulário).

    InputGrid é um dataclass plano (só str/int/float, sem campo aninhado) —
    `dataclasses.asdict` reflete os campos automaticamente, sem precisar
    listar os 27 campos à mão (e sem risco de esquecer um se o motor ganhar
    campo novo)."""
    try:
        from dataclasses import asdict
        from motor_viabilidade.exemplos import exemplo_planilha_original
        grid = exemplo_planilha_original().grid
        if grid is None:
            return None
        return asdict(grid)
    except Exception:
        return None


# ── Módulos 3-9: mesmo par (get_*_cls, exemplo_*_payload) dos módulos acima.
# `exemplo_planilha_original()` só carrega load/grid/solar/bess_ponta/cf — os
# outros (gen_ponta, gen_form, bess_form, new_grid) não têm dado de exemplo
# na planilha de referência; a rota /exemplo devolve 503 igual já fazia pra
# load/grid quando o motor está indisponível (mesmo tratamento de ausência,
# reaproveitado, não um caso novo).


def get_input_solar_scdee_cls() -> Optional[type]:
    try:
        from motor_viabilidade import InputSolarSCDEE
        return InputSolarSCDEE
    except Exception:
        return None


def exemplo_solar_scdee_payload() -> Optional[dict[str, Any]]:
    """InputSolarSCDEE tem 2 campos aninhados que não são dataclass
    (`cronograma_transicao: dict`, `dados_sonda/dados_pvgis/dados_tmy: dict`,
    `potencia_gerada_kw/potencia_injetada_kw: list[list]`) — `asdict` ainda
    funciona (só recursa em dataclass aninhado, dict/list passam direto)."""
    try:
        from dataclasses import asdict
        from motor_viabilidade.exemplos import exemplo_planilha_original
        solar = exemplo_planilha_original().solar
        if solar is None:
            return None
        return asdict(solar)
    except Exception:
        return None


def get_input_bess_ponta_cls() -> Optional[type]:
    try:
        from motor_viabilidade import InputBESSPonta
        return InputBESSPonta
    except Exception:
        return None


def exemplo_bess_ponta_payload() -> Optional[dict[str, Any]]:
    try:
        from dataclasses import asdict
        from motor_viabilidade.exemplos import exemplo_planilha_original
        bess = exemplo_planilha_original().bess_ponta
        if bess is None:
            return None
        return asdict(bess)
    except Exception:
        return None


def get_input_gerador_ponta_cls() -> Optional[type]:
    try:
        from motor_viabilidade import InputGeradorPonta
        return InputGeradorPonta
    except Exception:
        return None


def get_input_gerador_formador_cls() -> Optional[type]:
    try:
        from motor_viabilidade import InputGeradorFormador
        return InputGeradorFormador
    except Exception:
        return None


def get_input_bess_formador_cls() -> Optional[type]:
    try:
        from motor_viabilidade import InputBESSFormador
        return InputBESSFormador
    except Exception:
        return None


def get_input_new_grid_cls() -> Optional[type]:
    try:
        from motor_viabilidade import InputNewGrid
        return InputNewGrid
    except Exception:
        return None


def get_params_cf_cls() -> Optional[type]:
    try:
        from motor_viabilidade import ParamsCF
        return ParamsCF
    except Exception:
        return None


def exemplo_params_cf_payload() -> Optional[dict[str, Any]]:
    try:
        from dataclasses import asdict
        from motor_viabilidade.exemplos import exemplo_planilha_original
        params_cf = exemplo_planilha_original().params_cf
        if params_cf is None:
            return None
        return asdict(params_cf)
    except Exception:
        return None


def get_input_gridzero_cls() -> Optional[type]:
    try:
        from motor_viabilidade import InputGridZero
        return InputGridZero
    except Exception:
        return None


def get_calculadora_gridzero_cls() -> Optional[type]:
    try:
        from motor_viabilidade import CalculadoraGridZero
        return CalculadoraGridZero
    except Exception:
        return None
