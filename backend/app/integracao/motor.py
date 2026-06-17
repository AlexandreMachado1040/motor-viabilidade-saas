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
