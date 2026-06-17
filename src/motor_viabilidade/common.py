"""
Núcleo compartilhado do pacote ``motor_viabilidade``.

Reúne constantes e o logger usados por todos os módulos, evitando que cada
subpacote redefina valores ou reconfigure o logging.
"""
from __future__ import annotations

import logging

log = logging.getLogger("motor_viabilidade")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez"]
HORAS = list(range(24))

__all__ = ["log", "MESES", "HORAS"]
