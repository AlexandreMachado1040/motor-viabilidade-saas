"""MOD 8 — Custo de implantação de nova rede elétrica."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..InputGrid import InputGrid


@dataclass
class InputNewGrid:
    """Módulo 8 — Custo de implantação de nova rede elétrica."""
    capex_r: float = 15_000_000.0
    grid: "Optional[InputGrid]" = None


__all__ = ["InputNewGrid"]
