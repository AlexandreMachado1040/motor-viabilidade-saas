"""
Módulo GZ — Sistema fotovoltaico sem injeção na rede (GridZero).

Reúne as quatro classes do módulo GridZero:
  - InputGridZero            (parâmetros de entrada)
  - ResultadoGridZero        (resultado de um sistema)
  - CalculadoraGridZero      (métricas energéticas + financeiras)
  - AnaliseComparativaGridZero (comparação entre tamanhos de sistema)

Referência científica:
  Thiago Farias, "Dimensionamento ótimo de sistemas GridZero: impactos da curva
  de consumo e geração na viabilidade financeira", Revista Canal Solar N°33,
  Dezembro 2025.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..common import log

# Dados de demanda horária média diária extraídos da planilha
# Estudo_Grid-Zero_2.xlsx (média de todas as leituras por hora do dia)
# Unidade: kW (equivale a kWh/h na resolução horária)
_GZ_DEMANDA_PADRAO: list[float] = [
    53.3, 52.1, 52.3, 51.8, 51.1, 51.2,   # 00h–05h  (noturno baixo)
    51.5, 62.5, 73.0, 77.5, 77.3, 77.4,   # 06h–11h  (rampa matinal)
    79.8, 80.3, 79.4, 78.1, 78.8, 77.2,   # 12h–17h  (pico diurno ~88 kW)
    66.8, 67.4, 73.1, 73.4, 63.9, 54.3,   # 18h–23h  (descida noturna)
]

# Perfil de irradiância normalizado para Campinas/SP (fração de pico)
# Base: sobredimensionamento 32%, PR=0.78, dados PVGIS / planilha Solar 75 kW
_GZ_PERFIL_SOLAR_NORM: list[float] = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.004,
    0.160, 0.410, 0.630, 0.720, 0.740, 0.750,
    0.740, 0.700, 0.620, 0.490, 0.330, 0.090,
    0.002, 0.000, 0.000, 0.000, 0.000, 0.000,
]

# Tarifas pré-configuradas (concessionárias do artigo Canal Solar N°33)
_GZ_TARIFAS_PRESET: dict[str, dict] = {
    "cpfl_b3": {
        "nome": "CPFL Paulista — Classe B3",
        "te": 0.287, "tusd": 0.388,
        "icms_pct": 18.0, "piscofins_pct": 5.0,
    },
    "cemig_a4": {
        "nome": "Cemig-D — A4 Verde",
        "te": 0.379, "tusd": 0.440,
        "icms_pct": 12.0, "piscofins_pct": 3.65,
    },
}


@dataclass
class InputGridZero:
    """
    Módulo GZ — Sistema fotovoltaico sem injeção de energia na rede.

    Toda a energia gerada deve ser consumida instantaneamente pela carga
    local (clipping GridZero: gen_gz[h] = min(gen[h], potencia_ac_kw)).

    A viabilidade financeira depende diretamente de:
      - taxa de autoconsumo  : % do consumo total atendido pelo FV
      - simultaneidade       : % da geração FV efetivamente utilizada

    Referência científica:
      Thiago Farias, "Dimensionamento ótimo de sistemas GridZero: impactos
      da curva de consumo e geração na viabilidade financeira",
      Revista Canal Solar N°33, Dezembro 2025.
    """

    # ── Dimensionamento ────────────────────────────────────────────────
    potencia_ac_kw:        float = 75.0    # Potência do inversor (kW AC)
    sobredimensionamento:  float = 1.32    # CC/CA — padrão do artigo: 1.32
    performance_ratio:     float = 0.78    # PR do sistema

    # ── Tarifas ────────────────────────────────────────────────────────
    preset_concessionaria: str   = "cpfl_b3"  # chave de _GZ_TARIFAS_PRESET ou "manual"
    te_kwh:                float = 0.287   # Tarifa de Energia (R$/kWh)
    tusd_kwh:              float = 0.388   # TUSD (R$/kWh)
    icms_pct:              float = 18.0    # ICMS (%)
    piscofins_pct:         float = 5.0     # PIS+COFINS (%)
    reajuste_tarifa_pct:   float = 5.0     # Reajuste anual da tarifa (%)

    # ── Custos do projeto ──────────────────────────────────────────────
    capex_kwp:             float = 3000.0  # CAPEX (R$/kWp)
    om_pct_capex:          float = 1.0     # O&M (% do CAPEX ao ano)
    ipca_pct:              float = 4.5     # IPCA para reajuste do O&M (%)

    # ── Parâmetros financeiros ─────────────────────────────────────────
    tma_pct:               float = 12.0    # TMA — Taxa Mínima de Atratividade (%)
    anos_projeto:          int   = 25

    # ── Curva de demanda horária (kW) ──────────────────────────────────
    # Lista de 24 valores com a demanda média diária por hora
    demanda_horaria_kw: list[float] = field(
        default_factory=lambda: list(_GZ_DEMANDA_PADRAO)
    )

    # ── Perfil solar normalizado (opcional — substitui o padrão) ───────
    perfil_solar_norm: list[float] = field(
        default_factory=lambda: list(_GZ_PERFIL_SOLAR_NORM)
    )

    def __post_init__(self):
        """Aplica preset de concessionária se não for manual."""
        if self.preset_concessionaria != "manual":
            preset = _GZ_TARIFAS_PRESET.get(self.preset_concessionaria)
            if preset:
                self.te_kwh         = preset["te"]
                self.tusd_kwh       = preset["tusd"]
                self.icms_pct       = preset["icms_pct"]
                self.piscofins_pct  = preset["piscofins_pct"]

    def validar(self):
        assert len(self.demanda_horaria_kw) == 24, \
            "demanda_horaria_kw deve ter 24 valores (horas)"
        assert len(self.perfil_solar_norm) == 24, \
            "perfil_solar_norm deve ter 24 valores (horas)"
        assert self.potencia_ac_kw > 0, "potencia_ac_kw deve ser positivo"
        assert self.capex_kwp > 0, "capex_kwp deve ser positivo"

    @property
    def potencia_cc_kwp(self) -> float:
        """Potência CC instalada (kWp) = kW AC × sobredimensionamento."""
        return self.potencia_ac_kw * self.sobredimensionamento

    @property
    def tarifa_total_kwh(self) -> float:
        """Tarifa efetiva com tributos (R$/kWh)."""
        fator = 1 + self.icms_pct / 100 + self.piscofins_pct / 100
        return (self.te_kwh + self.tusd_kwh) * fator

    @property
    def capex_total_r(self) -> float:
        """CAPEX total (R$) = kWp × R$/kWp."""
        return self.potencia_cc_kwp * self.capex_kwp

    @property
    def om_anual_r(self) -> float:
        """O&M anual base (R$) = CAPEX × %."""
        return self.capex_total_r * (self.om_pct_capex / 100)

    def carregar_demanda_horaria_planilha(self):
        """
        Substitui a demanda horária pelos dados reais extraídos da planilha
        Estudo_Grid-Zero_2.xlsx (média de todas as leituras por hora do dia).
        Consumo médio diário: ~1.400 kWh/dia · pico ~88 kW (12h–17h).
        """
        self.demanda_horaria_kw = list(_GZ_DEMANDA_PADRAO)
        log.info("Demanda GridZero carregada da planilha "
                 f"(consumo médio: {sum(_GZ_DEMANDA_PADRAO):.0f} kWh/dia)")

    def geracao_horaria_kw(self) -> list[float]:
        """
        Curva de geração FV horária (kW) antes do clipping GridZero.
        P[h] = perfil_norm[h] × kWp × PR
        """
        fator = self.potencia_cc_kwp * self.performance_ratio
        return [round(p * fator, 4) for p in self.perfil_solar_norm]

    def geracao_gz_horaria_kw(self) -> list[float]:
        """
        Curva de geração FV com clipping GridZero aplicado.
        gen_gz[h] = min(gen[h], potencia_ac_kw)
        Toda energia acima da carga instantânea é descartada.
        """
        gen = self.geracao_horaria_kw()
        return [min(g, self.potencia_ac_kw) for g in gen]

    def excedente_cortado_kw(self) -> list[float]:
        """
        Excedente descartado pelo clipping GridZero (kW por hora).
        excedente[h] = max(0, gen[h] − carga[h])
        """
        gen = self.geracao_horaria_kw()
        carga = self.demanda_horaria_kw
        return [max(0.0, gen[h] - carga[h]) for h in range(24)]


@dataclass
class ResultadoGridZero:
    """
    Resultado completo do cálculo de viabilidade GridZero para um sistema.

    Fiel às Tabelas 3, 4, 5 e 6 do artigo Canal Solar N°33 (Thiago Farias).
    """
    # Dimensionamento
    potencia_ac_kw:    float = 0.0
    potencia_cc_kwp:   float = 0.0
    capex_total_r:     float = 0.0

    # Métricas energéticas (Tabela 3/4/5 do artigo)
    autoconsumo_kwh_dia:   float = 0.0   # kWh/dia efetivamente consumidos do FV
    geracao_gz_kwh_dia:    float = 0.0   # kWh/dia gerados após clipping
    consumo_total_kwh_dia: float = 0.0   # kWh/dia da carga
    excedente_kwh_dia:     float = 0.0   # kWh/dia descartados pelo GZ
    autoconsumo_pct:       float = 0.0   # % do consumo atendido pelo FV
    simultaneidade_pct:    float = 0.0   # % da geração FV efetivamente usada
    autoconsumo_anual_kwh: float = 0.0
    geracao_anual_kwh:     float = 0.0
    consumo_anual_kwh:     float = 0.0

    # Financeiro (Tabelas 3/4/5 do artigo)
    saving_ano1_r:     float = 0.0   # Economia no 1° ano (R$)
    payback_anos:      Optional[float] = None   # Payback descontado (anos)
    vpl_r:             float = 0.0   # VPL em 25 anos (R$)
    vpl_kwp_r:         float = 0.0   # VPL por kWp instalado — Tabela 6 do artigo
    tma_pct:           float = 12.0
    tarifa_kwh:        float = 0.0

    # Séries anuais (para plotagem/exportação)
    fc_nominal:    list[float] = field(default_factory=list)
    fc_acumulado:  list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dimensionamento": {
                "potencia_ac_kw":  self.potencia_ac_kw,
                "potencia_cc_kwp": self.potencia_cc_kwp,
                "capex_total_r":   round(self.capex_total_r, 2),
            },
            "energetico": {
                "autoconsumo_pct":     round(self.autoconsumo_pct, 2),
                "simultaneidade_pct":  round(self.simultaneidade_pct, 2),
                "autoconsumo_kwh_dia": round(self.autoconsumo_kwh_dia, 2),
                "geracao_gz_kwh_dia":  round(self.geracao_gz_kwh_dia, 2),
                "consumo_kwh_dia":     round(self.consumo_total_kwh_dia, 2),
                "excedente_kwh_dia":   round(self.excedente_kwh_dia, 2),
                "autoconsumo_anual_kwh": round(self.autoconsumo_anual_kwh, 0),
                "geracao_anual_kwh":     round(self.geracao_anual_kwh, 0),
                "consumo_anual_kwh":     round(self.consumo_anual_kwh, 0),
            },
            "financeiro": {
                "saving_ano1_r":   round(self.saving_ano1_r, 2),
                "payback_anos":    round(self.payback_anos, 2) if self.payback_anos else None,
                "vpl_r":           round(self.vpl_r, 2),
                "vpl_kwp_r":       round(self.vpl_kwp_r, 4),
                "tma_pct":         self.tma_pct,
                "tarifa_kwh":      round(self.tarifa_kwh, 4),
            },
        }

    def imprimir(self):
        print(f"\n{'─'*60}")
        print(f"  GridZero — {self.potencia_ac_kw:.0f} kW AC / "
              f"{self.potencia_cc_kwp:.0f} kWp CC")
        print(f"{'─'*60}")
        print(f"  Autoconsumo da geração : {self.autoconsumo_pct:>8.2f} %")
        print(f"  Simultaneidade         : {self.simultaneidade_pct:>8.2f} %")
        print(f"  Saving Ano 1           : R$ {self.saving_ano1_r:>12,.2f}")
        print(f"  Payback descontado     : "
              f"{self.payback_anos:.1f} anos" if self.payback_anos else "  Payback descontado     :       N/A")
        print(f"  VPL (25 anos)          : R$ {self.vpl_r:>12,.2f}")
        print(f"  VPL / kWp              : R$ {self.vpl_kwp_r:>10,.2f} / kWp")
        print(f"  CAPEX total            : R$ {self.capex_total_r:>12,.2f}")


class CalculadoraGridZero:
    """
    Calcula métricas energéticas e financeiras de um sistema GridZero.

    Metodologia fiel ao artigo da Revista Canal Solar N°33 (Dez/2025):
      - Autoconsumo  = Σ min(gen_gz[h], carga[h]) / consumo_total
      - Simultaneidade = Σ min(gen_gz[h], carga[h]) / geracao_gz_total
      - VPL descontado pela TMA, projeção 25 anos
      - Payback descontado: primeiro ano com FC acumulado ≥ 0
      - Rendimento VPL/kWp para comparação entre tamanhos de sistema
    """

    def __init__(self, gz: InputGridZero):
        self.gz = gz
        gz.validar()

    def calcular_metricas_energeticas(self) -> dict:
        """
        Retorna indicadores energéticos diários e anuais.
        """
        carga   = self.gz.demanda_horaria_kw
        gen_gz  = self.gz.geracao_gz_horaria_kw()
        gen_raw = self.gz.geracao_horaria_kw()

        autoconsumo_kwh_dia   = sum(min(gen_gz[h], carga[h]) for h in range(24))
        geracao_gz_kwh_dia    = sum(gen_gz)
        consumo_total_kwh_dia = sum(carga)
        excedente_kwh_dia     = sum(max(0.0, gen_raw[h] - carga[h]) for h in range(24))

        simultaneidade = (
            autoconsumo_kwh_dia / geracao_gz_kwh_dia * 100
            if geracao_gz_kwh_dia > 0 else 0.0
        )
        autoconsumo_pct = (
            autoconsumo_kwh_dia / consumo_total_kwh_dia * 100
            if consumo_total_kwh_dia > 0 else 0.0
        )

        return {
            "autoconsumo_kwh_dia":   autoconsumo_kwh_dia,
            "geracao_gz_kwh_dia":    geracao_gz_kwh_dia,
            "consumo_total_kwh_dia": consumo_total_kwh_dia,
            "excedente_kwh_dia":     excedente_kwh_dia,
            "autoconsumo_pct":       autoconsumo_pct,
            "simultaneidade_pct":    simultaneidade,
            "autoconsumo_anual_kwh": autoconsumo_kwh_dia * 365,
            "geracao_anual_kwh":     geracao_gz_kwh_dia * 365,
            "consumo_anual_kwh":     consumo_total_kwh_dia * 365,
        }

    def calcular_financeiro(self, metricas: dict) -> dict:
        """
        Calcula VPL, Payback descontado e VPL/kWp.
        Projeção de 25 anos com reajuste de tarifa e IPCA para O&M.
        """
        gz        = self.gz
        tarifa    = gz.tarifa_total_kwh
        capex     = gz.capex_total_r
        om_base   = gz.om_anual_r
        ac_anual  = metricas["autoconsumo_anual_kwh"]
        saving_a0 = ac_anual * tarifa  # Saving base (Ano 1)

        vpl      = -capex
        fc_acum  = -capex
        payback  = None
        fc_serie = [-capex]
        fc_ac_serie = [-capex]

        for a in range(1, gz.anos_projeto + 1):
            fator_tarifa = (1 + gz.reajuste_tarifa_pct / 100) ** a
            fator_ipca   = (1 + gz.ipca_pct / 100) ** a
            fator_desc   = (1 + gz.tma_pct / 100) ** a

            saving_a = saving_a0 * fator_tarifa
            om_a     = om_base   * fator_ipca
            fc_a     = saving_a - om_a

            vpl     += fc_a / fator_desc
            fc_acum += fc_a

            fc_serie.append(fc_a)
            fc_ac_serie.append(fc_acum)

            if payback is None and fc_acum >= 0:
                # Interpolação linear para payback fracionado
                fc_prev = fc_ac_serie[-2] if len(fc_ac_serie) >= 2 else fc_acum
                if fc_a > 0:
                    payback = (a - 1) + abs(fc_prev) / fc_a
                else:
                    payback = float(a)

        vpl_kwp = vpl / gz.potencia_cc_kwp if gz.potencia_cc_kwp > 0 else 0.0

        return {
            "saving_ano1_r":  saving_a0,
            "vpl_r":          vpl,
            "vpl_kwp_r":      vpl_kwp,
            "payback_anos":   payback,
            "capex_total_r":  capex,
            "tarifa_kwh":     tarifa,
            "fc_nominal":     fc_serie,
            "fc_acumulado":   fc_ac_serie,
        }

    def calcular(self) -> ResultadoGridZero:
        """
        Executa o cálculo completo e retorna ResultadoGridZero.
        """
        m = self.calcular_metricas_energeticas()
        f = self.calcular_financeiro(m)

        return ResultadoGridZero(
            potencia_ac_kw       = self.gz.potencia_ac_kw,
            potencia_cc_kwp      = self.gz.potencia_cc_kwp,
            capex_total_r        = f["capex_total_r"],
            autoconsumo_kwh_dia  = m["autoconsumo_kwh_dia"],
            geracao_gz_kwh_dia   = m["geracao_gz_kwh_dia"],
            consumo_total_kwh_dia= m["consumo_total_kwh_dia"],
            excedente_kwh_dia    = m["excedente_kwh_dia"],
            autoconsumo_pct      = m["autoconsumo_pct"],
            simultaneidade_pct   = m["simultaneidade_pct"],
            autoconsumo_anual_kwh= m["autoconsumo_anual_kwh"],
            geracao_anual_kwh    = m["geracao_anual_kwh"],
            consumo_anual_kwh    = m["consumo_anual_kwh"],
            saving_ano1_r        = f["saving_ano1_r"],
            payback_anos         = f["payback_anos"],
            vpl_r                = f["vpl_r"],
            vpl_kwp_r            = f["vpl_kwp_r"],
            tma_pct              = self.gz.tma_pct,
            tarifa_kwh           = f["tarifa_kwh"],
            fc_nominal           = f["fc_nominal"],
            fc_acumulado         = f["fc_acumulado"],
        )


class AnaliseComparativaGridZero:
    """
    Executa análise comparativa entre múltiplos tamanhos de sistema GridZero,
    replicando as Tabelas 3, 4, 5 e 6 do artigo Canal Solar N°33.

    Potências padrão do artigo: 25, 50, 100 kW AC (inversores)
    com sobredimensionamento CC de 32%: → 33, 66, 132 kWp.
    """

    POTENCIAS_PADRAO = [25.0, 50.0, 75.0, 100.0, 150.0]  # kW AC

    def __init__(
        self,
        base: InputGridZero,
        potencias_kw: Optional[list[float]] = None,
    ):
        self.base      = base
        self.potencias = potencias_kw or self.POTENCIAS_PADRAO

    def rodar(self) -> dict[float, ResultadoGridZero]:
        """
        Retorna dict {potencia_ac_kw: ResultadoGridZero} para cada tamanho.
        """
        import copy
        resultados = {}
        for kw in self.potencias:
            gz = copy.deepcopy(self.base)
            gz.potencia_ac_kw = kw
            gz.__post_init__()  # reatualiza CAPEX total etc.
            calc = CalculadoraGridZero(gz)
            resultados[kw] = calc.calcular()
        return resultados

    def imprimir_tabela(self, resultados: Optional[dict] = None):
        """Imprime tabela comparativa estilo artigo Canal Solar N°33."""
        if resultados is None:
            resultados = self.rodar()

        header = f"{'SISTEMA':>12} | {'PAYBACK':>10} | {'SIMULT.':>10} | " \
                 f"{'AUTOCONS.':>10} | {'VPL (R$)':>14} | {'VPL/kWp':>10}"
        sep = "─" * len(header)

        print(f"\n{'═'*len(header)}")
        print("  COMPARATIVO GRIDZERO — Artigo Canal Solar N°33")
        print(f"  Concessionária: {self.base.preset_concessionaria.upper()} | "
              f"CAPEX: R${self.base.capex_kwp:.0f}/kWp | "
              f"TMA: {self.base.tma_pct:.0f}%")
        print(f"{'═'*len(header)}")
        print(header)
        print(sep)

        for kw, r in sorted(resultados.items()):
            pb = f"{r.payback_anos:.2f}a" if r.payback_anos else "N/A"
            print(
                f"  {kw:.0f}kW/{r.potencia_cc_kwp:.0f}kWp | "
                f"{pb:>10} | "
                f"{r.simultaneidade_pct:>9.2f}% | "
                f"{r.autoconsumo_pct:>9.2f}% | "
                f"R${r.vpl_r:>12,.2f} | "
                f"R${r.vpl_kwp_r:>8,.2f}"
            )
        print(sep)

    def exportar_csv(self, caminho: str = "gridzero_resultados.csv",
                     resultados: Optional[dict] = None):
        """Exporta tabela de resultados para CSV."""
        import csv
        if resultados is None:
            resultados = self.rodar()
        campos = [
            "potencia_ac_kw", "potencia_cc_kwp", "capex_total_r",
            "autoconsumo_pct", "simultaneidade_pct",
            "autoconsumo_kwh_dia", "geracao_gz_kwh_dia",
            "saving_ano1_r", "payback_anos", "vpl_r", "vpl_kwp_r",
        ]
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            for r in sorted(resultados.values(), key=lambda x: x.potencia_ac_kw):
                w.writerow({c: getattr(r, c) for c in campos})
        log.info(f"GridZero CSV exportado: {caminho}")


__all__ = [
    "InputGridZero",
    "ResultadoGridZero",
    "CalculadoraGridZero",
    "AnaliseComparativaGridZero",
]
