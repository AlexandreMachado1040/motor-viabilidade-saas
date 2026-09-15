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

# As matrizes 12×24 (demanda, geração) são o DIA TÍPICO de cada mês: somar as
# 24 horas dá kWh/dia, e o mês precisa multiplicar pelos dias.
DIAS_NO_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Dias com horário de ponta (seg–sex) por mês, contados em 2025. Feriados não
# são descontados — superestima levemente o que o BESS de ponta opera.
DIAS_UTEIS_MES = [23, 20, 21, 22, 22, 21, 23, 21, 22, 23, 20, 23]

__all__ = ["log", "MESES", "HORAS", "DIAS_NO_MES", "DIAS_UTEIS_MES"]
