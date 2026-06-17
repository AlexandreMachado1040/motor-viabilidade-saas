"""Controle de acesso por módulo (licenciamento SaaS modular)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LicencaModulos:
    """
    Controla quais módulos o usuário contratou.
    Cada flag True = módulo liberado.
    """
    load:       bool = True   # Módulo 1  — Carga
    grid:       bool = True   # Módulo 2  — Tarifa/Grid
    solar:      bool = False  # Módulo 3  — Solar SCDEE
    bess_ponta: bool = False  # Módulo 4  — BESS Ponta
    gen_ponta:  bool = False  # Módulo 5  — Gerador Ponta
    gen_form:   bool = False  # Módulo 6  — Gerador Formador
    bess_form:  bool = False  # Módulo 7  — BESS Formador
    new_grid:   bool = False  # Módulo 8  — Nova Rede
    cf:         bool = True   # Módulo 9  — Fluxo de Caixa
    summary:    bool = True   # Módulo 10 — Sumário
    gridzero:   bool = False  # Módulo GZ — GridZero (sem injeção na rede)

    def requer(self, modulo: str):
        if not getattr(self, modulo, False):
            raise PermissionError(
                f"Módulo '{modulo}' não contratado. "
                "Adquira a licença correspondente para acesso."
            )


__all__ = ["LicencaModulos"]
