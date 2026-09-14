"""Validação e cálculo de derivados do MOD 2 — InputGrid."""
from __future__ import annotations

from ...integracao.motor import get_input_grid_cls
from .schemas import GridResumo, InputGridPayload


def validar_grid(p: InputGridPayload) -> GridResumo:
    # InputGrid é um dataclass plano sem `.validar()` (ao contrário de
    # InputLoad) — não há estrutura variável pra checar (12 meses, 24 horas
    # etc.), só valores escalares já tipados/validados pelo Pydantic. "valido"
    # existe no schema por consistência com os demais módulos, mas aqui é
    # sempre True: não há combinação de floats que devesse ser rejeitada
    # nesta camada (tarifa negativa é uma decisão de dado, não um erro
    # estrutural — a concessionária real pode ter desconto/crédito).
    InputGrid = get_input_grid_cls()
    if InputGrid is not None:
        grid = InputGrid(**p.model_dump())
        tarifa_ponta = grid.tarifa_ponta
        tarifa_fp = grid.tarifa_fp
    else:
        tarifa_ponta = p.tusd_ponta + p.te_ponta
        tarifa_fp = p.tusd_fp + p.te_fp

    return GridResumo(valido=True, erros=[], tarifa_ponta=tarifa_ponta, tarifa_fp=tarifa_fp)


__all__ = ["validar_grid"]
