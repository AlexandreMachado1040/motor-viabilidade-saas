"""Integra SONDA / PVGIS / TMY em uma matriz 12×24 de potência solar (kW AC)."""
from __future__ import annotations

import math

from ..common import log


class IntegradorSolarimetrico:
    """
    Integra os três motores solarimétricos:
      sonda_collector.py · pvgis_collector.py · tmy_generator.py
    Resultado: matriz 12×24 de potência solar (kW AC).
    """

    def __init__(self, potencia_kwp: float, lat: float, lon: float,
                 fonte: str = "tmy", station: str = "BRB",
                 performance_ratio: float = 0.78, eta_inversor: float = 0.98):
        self.kwp = potencia_kwp
        self.lat, self.lon = lat, lon
        self.fonte, self.station = fonte, station
        self.pr, self.eta_inv = performance_ratio, eta_inversor

    def obter_irradiancia_horaria(self) -> dict:
        if self.fonte == "sonda":   return self._obter_sonda()
        if self.fonte == "pvgis":   return self._obter_pvgis()
        if self.fonte == "tmy":     return self._obter_tmy()
        return {}

    def _obter_sonda(self) -> dict:
        try:
            from sonda_collector import coletar_sonda
            dados = coletar_sonda(station=self.station, salvar_raw=False,
                                  salvar_horario=True, salvar_diario=False)
            return {"horario": dados.get("horario")}
        except ImportError:
            log.warning("sonda_collector não encontrado.")
            return {}

    def _obter_pvgis(self) -> dict:
        try:
            from pvgis_collector import obter_serie_horaria, LocalizacaoPV
            return {"horario": obter_serie_horaria(LocalizacaoPV(lat=self.lat, lon=self.lon))}
        except ImportError:
            log.warning("pvgis_collector não encontrado.")
            return {}

    def _obter_tmy(self) -> dict:
        try:
            from tmy_generator import tmy_de_pvgis, ConfigTMY
            config = ConfigTMY(lat=self.lat, lon=self.lon)
            resultado = tmy_de_pvgis(lat=self.lat, lon=self.lon, config=config,
                                     dir_saida="./tmy_cache", formatos=["parquet"])
            return {"tmy": resultado.tmy}
        except ImportError:
            log.warning("tmy_generator não encontrado.")
            return {}

    def gerar_matriz_potencia_12x24(self) -> list[list[float]]:
        dados = self.obter_irradiancia_horaria()
        df = dados.get("tmy") or dados.get("horario")
        if df is None or (hasattr(df, "empty") and df.empty):
            log.warning("Dados solarimétricos indisponíveis — matriz zerada.")
            return [[0.0]*24 for _ in range(12)]
        fator = (self.kwp / 1000.0) * self.pr * self.eta_inv
        matriz = []
        for mes in range(1, 13):
            df_mes = df[df["timestamp"].dt.month == mes]
            linha = []
            for h in range(24):
                ghi = df_mes[df_mes["timestamp"].dt.hour == h]["ghi_wm2"].mean()
                ghi = 0.0 if (ghi is None or (
                    hasattr(ghi, "__float__") and math.isnan(float(ghi)))) else float(ghi)
                linha.append(round(ghi * fator, 4))
            matriz.append(linha)
        return matriz


__all__ = ["IntegradorSolarimetrico"]
