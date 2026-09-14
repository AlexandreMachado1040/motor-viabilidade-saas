"""Validação do MOD 8 — InputNewGrid."""
from __future__ import annotations

from .schemas import InputNewGridPayload, NewGridResumo


def validar_new_grid(p: InputNewGridPayload) -> NewGridResumo:
    # InputNewGrid não tem `.validar()` nem propriedade derivada (só
    # `capex_r` + a referência cruzada a InputGrid, fora de escopo aqui — ver
    # schemas.py). Não há nada de negócio pra calcular além do que o Pydantic
    # já valida (tipo/presença); "valido" existe por consistência com os
    # demais módulos.
    return NewGridResumo(valido=True, erros=[], capex_r=p.capex_r)


__all__ = ["validar_new_grid"]
