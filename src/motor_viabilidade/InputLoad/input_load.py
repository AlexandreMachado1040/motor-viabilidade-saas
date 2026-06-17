"""MOD 1 — Memória de massa de demanda e energia (carga)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InputLoad:
    """Módulo 1 — Memória de massa de demanda e energia."""
    demanda_maxima_kw:   float = 238.56
    demanda_kw:          list[list[float]] = field(default_factory=list)
    energia_ponta_kwh:   list[float]       = field(default_factory=list)
    energia_fp_kwh:      list[float]       = field(default_factory=list)

    def validar(self):
        assert len(self.demanda_kw) == 12, "demanda_kw deve ter 12 meses"
        for i, linha in enumerate(self.demanda_kw):
            assert len(linha) == 24, f"demanda_kw[{i}] deve ter 24 horas"
        assert len(self.energia_ponta_kwh) == 12
        assert len(self.energia_fp_kwh) == 12

    @property
    def energia_equivalente_kwh(self) -> list[float]:
        return [p + fp for p, fp in zip(self.energia_ponta_kwh, self.energia_fp_kwh)]

    @property
    def energia_ponta_total(self) -> float:
        return sum(self.energia_ponta_kwh)

    @property
    def energia_fp_total(self) -> float:
        return sum(self.energia_fp_kwh)


__all__ = ["InputLoad"]
