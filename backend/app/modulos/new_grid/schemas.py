"""Schemas do MOD 8 — InputNewGrid (custo de implantação de nova rede).

`InputNewGrid.grid: Optional[InputGrid]` (referência cruzada a outro módulo)
não entra no payload — validar um módulo isolado não resolve dependência de
outro; quem monta o estudo completo (fora do escopo desta rota) decide se
`new_grid` reaproveita o `InputGrid` principal ou tem um próprio."""
from __future__ import annotations

from pydantic import BaseModel, Field


class InputNewGridPayload(BaseModel):
    capex_r: float = 15_000_000.0


class NewGridResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
    capex_r: float = 0.0
