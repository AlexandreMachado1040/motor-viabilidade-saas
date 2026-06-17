"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MOTOR DE ESTUDO DE VIABILIDADE — SISTEMA HÍBRIDO                           ║
║  Baseado em: ESTUDO_DE_VIABILIDADE_Híbrido_27-06-2024                       ║
║  Módulos licenciáveis por assinatura (SaaS modular)                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Módulos disponíveis (licenciáveis individualmente):
  MOD_LOAD       - Input de Carga (memória de massa)
  MOD_GRID       - Tarifa e Encargos da Distribuidora (+ API ANEEL)
  MOD_SOLAR      - Solar SCDEE (GD / compensação) + integração SONDA/PVGIS/TMY
  MOD_BESS_PONTA - Bateria para redução de ponta
  MOD_GEN_PONTA  - Gerador diesel de ponta
  MOD_GEN_FORM   - Gerador formador de rede (off-grid/híbrido)
  MOD_BESS_FORM  - BESS formador de rede
  MOD_NEW_GRID   - Nova rede elétrica
  MOD_CF         - Fluxo de Caixa e Análise Econômica (TIR, VPL, Payback)
  MOD_SUMMARY    - Sumário executivo e comparação de cenários
  MOD_GRIDZERO   - Sistema sem injeção na rede (GridZero)
                   Ref.: "Dimensionamento ótimo de sistemas GridZero: impactos
                   da curva de consumo e geração na viabilidade financeira"
                   Thiago Farias — Revista Canal Solar N°33, Dez/2025

Dependências:
  pip install numpy pandas requests msal python-dateutil

Uso básico:
  from motor_viabilidade import EstudoViabilidade, LicencaModulos, InputGridZero
  lic    = LicencaModulos(load=True, grid=True, gridzero=True, cf=True)
  estudo = EstudoViabilidade(lic)
  estudo.carregar_grid(params_grid)
  gz = InputGridZero(potencia_ac_kw=75, capex_kwp=3000.0, ...)
  gz.carregar_demanda_horaria_planilha()   # dados reais da planilha
  resultado = estudo.calcular_gridzero(gz)
  print(resultado)
"""

from __future__ import annotations
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

log = logging.getLogger("motor_viabilidade")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

MESES = ["jan","fev","mar","abr","mai","jun",
         "jul","ago","set","out","nov","dez"]
HORAS = list(range(24))

# ═══════════════════════════════════════════════════════════════════════
# LICENÇA MODULAR
# ═══════════════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════════════
# MÓDULO 2 — API ANEEL (tarifas via Dynamics 365 / OData)
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class ConfigAPIANEEL:
    """
    Configuração de autenticação para o BI da ANEEL
    (Microsoft Dynamics 365 / Dataverse).

    O endpoint exige autenticação OAuth 2.0 via Azure AD (MSAL).
    Credenciais devem ser obtidas junto ao administrador do tenant ANEEL.
    """
    tenant_id:     str = "67ffc8c1-818a-4849-9314-1aa26812c317"
    client_id:     str = ""       # App registration na ANEEL
    client_secret: str = ""       # Secret do app registration
    base_url:      str = "https://csisolarcrmprod.crm16.dynamics.com"
    api_version:   str = "v9.2"
    order_id:      str = "ad670927-b765-f111-ab0c-002248e570e3"
    usar_cache:    bool = True
    cache_path:    str = "aneel_tarifas_cache.json"


class ClienteAPIANEEL:
    """
    Cliente para buscar tarifas diretamente do BI da ANEEL
    (Microsoft Dynamics 365 / Dataverse OData v4).
    Fluxo: MSAL client_credentials → Bearer token → OData query → cache JSON.
    """

    def __init__(self, config: ConfigAPIANEEL):
        self.cfg = config
        self._token: Optional[str] = None

    def _obter_token(self) -> str:
        try:
            import msal
            app = msal.ConfidentialClientApplication(
                client_id=self.cfg.client_id,
                client_credential=self.cfg.client_secret,
                authority=f"https://login.microsoftonline.com/{self.cfg.tenant_id}",
            )
            result = app.acquire_token_for_client(
                scopes=[f"{self.cfg.base_url}/.default"]
            )
            if "access_token" not in result:
                raise RuntimeError(
                    f"Falha ao obter token MSAL: {result.get('error_description')}"
                )
            return result["access_token"]
        except ImportError:
            raise ImportError("Instale msal: pip install msal")

    def buscar_tarifa_por_id(self, order_id: str = None) -> dict:
        import requests
        oid = order_id or self.cfg.order_id
        if not self._token:
            self._token = self._obter_token()
        url = (f"{self.cfg.base_url}/api/data/{self.cfg.api_version}"
               f"/csi_orders({oid})")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def buscar_tarifas_por_concessionaria(
        self, concessionaria: str, subgrupo: str, modalidade: str, ano_revisao: int,
    ) -> dict:
        import requests
        if not self._token:
            self._token = self._obter_token()
        filtro = (
            f"csi_concessionaria eq '{concessionaria}' and "
            f"csi_subgrupo eq '{subgrupo}' and "
            f"csi_modalidade eq '{modalidade}' and "
            f"csi_ano_revisao eq {ano_revisao}"
        )
        select = ",".join([
            "csi_tusd_ponta", "csi_tusd_fp", "csi_te_ponta", "csi_te_fp",
            "csi_demanda_sem_posto", "csi_demanda_geracao",
            "csi_tusd_fio_a_p", "csi_tusd_fio_b_p",
            "csi_tusd_fio_a_fp", "csi_tusd_fio_b_fp",
            "csi_fator_k", "csi_outros_p", "csi_outros_fp",
        ])
        url = (f"{self.cfg.base_url}/api/data/{self.cfg.api_version}"
               f"/csi_orders?$filter={filtro}&$select={select}&$top=1")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("value"):
            return data["value"][0]
        raise ValueError(
            f"Nenhuma tarifa encontrada para {concessionaria}/{subgrupo}/"
            f"{modalidade}/{ano_revisao} na API ANEEL."
        )

    def buscar_com_fallback(
        self, concessionaria: str, subgrupo: str, modalidade: str, ano_revisao: int,
    ) -> dict:
        import requests
        chave = f"{concessionaria}__{subgrupo}__{modalidade}__{ano_revisao}"
        try:
            dados = self.buscar_tarifas_por_concessionaria(
                concessionaria, subgrupo, modalidade, ano_revisao
            )
            if self.cfg.usar_cache:
                try:
                    import json as _j, pathlib
                    p = pathlib.Path(self.cfg.cache_path)
                    cache = _j.loads(p.read_text()) if p.exists() else {}
                    cache[chave] = dados
                    p.write_text(_j.dumps(cache, indent=2, ensure_ascii=False))
                except Exception:
                    pass
            return dados
        except Exception as e:
            log.warning(f"API ANEEL indisponível ({e}). Tentando cache local...")

        if self.cfg.usar_cache:
            try:
                import json as _j, pathlib
                p = pathlib.Path(self.cfg.cache_path)
                if p.exists():
                    cache = _j.loads(p.read_text())
                    if chave in cache:
                        log.info(f"Tarifas carregadas do cache: {self.cfg.cache_path}")
                        return cache[chave]
            except Exception:
                pass

        log.error("API ANEEL e cache local indisponíveis. "
                  "Preencha as tarifas manualmente via InputGrid.")
        return {}


# ═══════════════════════════════════════════════════════════════════════
# DATA CLASSES — parâmetros de entrada de cada módulo
# ═══════════════════════════════════════════════════════════════════════

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


@dataclass
class InputGrid:
    """Módulo 2 — Tarifas e encargos da concessionária."""
    concessionaria:        str   = "Cemig-D"
    ano_revisao:           int   = 2023
    subgrupo:              str   = "A4"
    modalidade:            str   = "Verde"
    tusd_ponta:            float = 1.326
    tusd_fp:               float = 0.118
    te_ponta:              float = 0.379
    te_fp:                 float = 0.232
    tusd_fio_a_p:          float = 0.25728
    tusd_fio_b_p:          float = 1.130074
    tusd_tfsee_p:          float = 0.000341
    tusd_pd_p:             float = 0.0093775
    te_pd_p:               float = 0.0027280
    outros_p:              float = 0.305195
    tusd_fio_a_fp:         float = 0.0
    tusd_fio_b_fp:         float = 0.0
    tusd_tfsee_fp:         float = 0.00042
    tusd_pd_fp:            float = 0.00042
    te_pd_fp:              float = 0.0028
    outros_fp:             float = 0.34640
    demanda_sem_posto:     float = 16.54
    tusd_fio_a_dem:        float = 5.544208
    tusd_fio_b_dem:        float = 13.513180
    outros_dem:            float = -2.520696
    demanda_geracao:       float = 9.45
    fator_k:               float = 4.8714
    demanda_contratada_kw: float = 250.488

    @property
    def tarifa_ponta(self) -> float:
        return self.tusd_ponta + self.te_ponta

    @property
    def tarifa_fp(self) -> float:
        return self.tusd_fp + self.te_fp

    @classmethod
    def de_api_aneel(cls, dados_api: dict) -> "InputGrid":
        g = cls()
        mapa = {
            "csi_tusd_ponta": "tusd_ponta", "csi_tusd_fp": "tusd_fp",
            "csi_te_ponta": "te_ponta",     "csi_te_fp": "te_fp",
            "csi_demanda_sem_posto": "demanda_sem_posto",
            "csi_demanda_geracao": "demanda_geracao",
            "csi_tusd_fio_a_p": "tusd_fio_a_p",
            "csi_tusd_fio_b_p": "tusd_fio_b_p",
            "csi_fator_k": "fator_k",
            "csi_outros_p": "outros_p",
            "csi_outros_fp": "outros_fp",
        }
        for api_key, attr in mapa.items():
            if api_key in dados_api and dados_api[api_key] is not None:
                setattr(g, attr, float(dados_api[api_key]))
        return g


@dataclass
class InputSolarSCDEE:
    """Módulo 3 — Sistema solar GD / compensação de energia elétrica."""
    estado:              str   = "São Paulo"
    potencia_ca_kw:      float = 211.27
    potencia_cc_kwp:     float = 300.0
    sobrecarga_inversor: float = 1.42
    capex_r:             float = 885000.0
    om_anual_r:          float = 1500.0
    degradacao_ano1:     float = 0.02
    degradacao_demais:   float = 0.0055
    custo_troca_inversor_r: float = 50000.0
    ano_troca_inversor:  int   = 12
    modalidade_gd:       str   = "GDIII"
    data_estudo_ano:     int   = 2024
    cronograma_transicao: dict = field(default_factory=lambda: {
        2023: 0.15, 2024: 0.30, 2025: 0.45, 2026: 0.60,
        2027: 0.75, 2028: 0.90,
    })
    tusd_ponta:          float = 1.326
    tusd_fp:             float = 0.118
    te_ponta:            float = 0.379
    te_fp:               float = 0.232
    tusd_fio_a_p:        float = 0.25728
    tusd_fio_b_p:        float = 1.130074
    outros_p:            float = 0.305195
    demanda_geracao_r:   float = 9.45
    potencia_gerada_kw:  list[list[float]] = field(default_factory=list)
    potencia_injetada_kw: list[list[float]] = field(default_factory=list)
    fonte_dados: str = "manual"
    dados_sonda: dict = field(default_factory=dict)
    dados_pvgis: dict = field(default_factory=dict)
    dados_tmy:   dict = field(default_factory=dict)

    @property
    def periodo_transicao_vigente(self) -> float:
        for a in sorted(self.cronograma_transicao.keys(), reverse=True):
            if self.data_estudo_ano >= a:
                return self.cronograma_transicao[a]
        return 0.0

    def energia_injetada_mensal_kwh(self) -> list[float]:
        return [abs(sum(self.potencia_injetada_kw[m]))
                if m < len(self.potencia_injetada_kw) else 0.0
                for m in range(12)]

    def energia_gerada_mensal_kwh(self) -> list[float]:
        return [sum(self.potencia_gerada_kw[m])
                if m < len(self.potencia_gerada_kw) else 0.0
                for m in range(12)]

    def calcular_opex_energia_mensal(self, grid: InputGrid) -> list[float]:
        result = []
        energia_inj = self.energia_injetada_mensal_kwh()
        ft = self.periodo_transicao_vigente
        for m in range(12):
            e = energia_inj[m]
            economia = e * (grid.te_fp + grid.tusd_fp - ft * grid.tusd_fio_b_fp)
            result.append(-economia)
        return result

    def calcular_opex_demanda_mensal(self, grid: InputGrid) -> list[float]:
        dem_red = self.potencia_ca_kw * grid.demanda_geracao / 12
        return [-dem_red] * 12


@dataclass
class InputBESSPonta:
    """Módulo 4 — Bateria para redução de ponta."""
    capex_r:                 float = 5_526_000.0
    custo_reposicao_r:       float = 5_526_000.0
    tempo_reposicao_anos:    int   = 14
    vida_util_anos:          int   = 14
    percentual_eol:          float = 0.60
    n_ciclos_dod80:          float = 4882.5
    n_ciclos_dod100:         float = 3906.0
    dod_operacional:         float = 0.80
    n_bms_por_br:            int   = 18
    n_bms_total:             int   = 180
    n_brs:                   int   = 10
    brs_serie:               int   = 1
    brs_paralelo:            int   = 10
    tensao_nominal_v:        float = 691.2
    resistencia_interna_mohm: float = 43.2
    coulombic_eff:           float = 0.953
    tensao_corte_carga_v:    float = 777.6
    tensao_corte_descarga_v: float = 583.2
    capacidade_c10_ah:       float = 2890.0
    corrente_max_carga_a:    float = 330.0
    corrente_max_descarga_a: float = 330.0
    potencia_max_carga_kw:   float = 228.096
    potencia_max_descarga_kw: float = 228.096
    perda_sistema:           float = 0.0115
    eta_pcs:                 float = 0.982
    eta_bateria:             float = 0.9885
    eta_sys:                 float = 0.99
    eta_total:               float = 0.961
    energia_dod80_kwh:       float = 1598.05
    energia_dod100_kwh:      float = 1997.57
    energia_dod80_pos_pcs:   float = 1535.73
    energia_dod100_pos_pcs:  float = 1919.66
    tempo_carga_h:           float = 7.006
    tempo_descarga_h:        float = 7.006

    def energia_eol_dod80_kwh(self) -> float:
        return self.energia_dod80_kwh * self.percentual_eol

    def calcular_opex_fp_energia(
        self, demanda_kw: list[list[float]], potencia_max_kw: float, grid: InputGrid
    ) -> float:
        total = 0.0
        for m in range(12):
            energia_carga = potencia_max_kw * self.tempo_carga_h / self.eta_total
            total += energia_carga * grid.tarifa_fp
        return total

    def calcular_saving_ponta(self, demanda_kw: list[list[float]], grid: InputGrid) -> float:
        total = 0.0
        for m in range(12):
            energia_descarga = self.potencia_max_descarga_kw * self.tempo_descarga_h
            total += energia_descarga * grid.tarifa_ponta
        return total


@dataclass
class InputGeradorPonta:
    """Módulo 5 — Gerador diesel de ponta."""
    capex_r:            float = 60_000.0
    om_anual_r:         float = 600.0
    vida_util_anos:     int   = 5
    potencia_kw:        float = 250.0
    reserva_girante:    float = 1.0
    consumo_min_lh:     float = 0.0
    consumo_max_lh:     float = 0.0
    custo_diesel_litro: float = 5.92
    coef_interceptacao: float = 0.0
    slope:              float = 0.0

    def custo_diesel_kwh(self) -> float:
        if self.consumo_max_lh > 0 and self.potencia_kw > 0:
            return self.consumo_max_lh * self.custo_diesel_litro / self.potencia_kw
        return 0.0


@dataclass
class InputGeradorFormador:
    """Módulo 6 — Gerador formador de rede."""
    capex_r:            float = 60_000.0
    om_anual_r:         float = 600.0
    vida_util_anos:     int   = 5
    potencia_kw:        float = 250.0
    custo_diesel_litro: float = 5.92

    def custo_diesel_kwh(self) -> float:
        return 0.0


@dataclass
class InputBESSFormador:
    """Módulo 7 — BESS formador de rede (off-grid / híbrido)."""
    capex_r:              float = 5_560_000.0
    custo_reposicao_r:    float = 5_560_000.0
    tempo_reposicao_anos: int   = 14
    vida_util_anos:       int   = 14
    energia_dod80_kwh:    float = 0.0
    eta_total:            float = 0.961


@dataclass
class SolarHibridoParams:
    """Parâmetros de geração solar para sistemas híbridos (BESS/GEN forming)."""
    potencia_cc_kwp:    float = 0.0
    capex_r:            float = 0.0
    om_anual_r:         float = 1500.0
    ano_troca_inversor: int   = 12
    custo_troca_inv_r:  float = 50000.0
    potencia_gerada_kw: list[list[float]] = field(default_factory=list)

    def energia_anual_kwh(self) -> float:
        return sum(sum(self.potencia_gerada_kw[m])
                   for m in range(len(self.potencia_gerada_kw)))


@dataclass
class InputNewGrid:
    """Módulo 8 — Custo de implantação de nova rede elétrica."""
    capex_r: float = 15_000_000.0
    grid: Optional[InputGrid] = None


@dataclass
class ParamsCF:
    """Parâmetros econômico-financeiros do fluxo de caixa."""
    taxa_desconto:         float = 0.08
    inflacao:              float = 0.0393
    anos_projeto:          int   = 25
    reajuste_tarifa_ponta: float = 0.010
    reajuste_tarifa_fp:    float = 0.000
    reajuste_demanda_spt:  float = 0.008
    reajuste_combustivel:  float = 0.010

    @property
    def taxa_desconto_real(self) -> float:
        return ((1 + self.taxa_desconto) / (1 + self.inflacao)) - 1


# ═══════════════════════════════════════════════════════════════════════
# MÓDULO GZ — INPUT GRIDZERO
# ═══════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════
# CALCULADORA GRIDZERO
# ═══════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════
# CALCULADORA DE OPEX GRID
# ═══════════════════════════════════════════════════════════════════════

class CalculadoraOPEXGrid:
    """Calcula o OPEX mensal/anual da tarifa de rede (baseline)."""

    def __init__(self, load: InputLoad, grid: InputGrid):
        self.load = load
        self.grid = grid

    def opex_tusd_ponta_mensal(self) -> list[float]:
        return [e * self.grid.tusd_ponta for e in self.load.energia_ponta_kwh]

    def opex_tusd_fp_mensal(self) -> list[float]:
        return [e * self.grid.tusd_fp for e in self.load.energia_fp_kwh]

    def opex_te_ponta_mensal(self) -> list[float]:
        return [e * self.grid.te_ponta for e in self.load.energia_ponta_kwh]

    def opex_te_fp_mensal(self) -> list[float]:
        return [e * self.grid.te_fp for e in self.load.energia_fp_kwh]

    def opex_demanda_spt_mensal(self) -> list[float]:
        return [self.load.demanda_maxima_kw * self.grid.demanda_sem_posto] * 12

    def opex_grid_total_mensal(self) -> list[float]:
        return [a+b+c+d+e for a,b,c,d,e in zip(
            self.opex_tusd_ponta_mensal(), self.opex_tusd_fp_mensal(),
            self.opex_te_ponta_mensal(),   self.opex_te_fp_mensal(),
            self.opex_demanda_spt_mensal(),
        )]

    def opex_grid_anual(self) -> float:
        return sum(self.opex_grid_total_mensal())

    def opex_fp_energia_anual(self) -> float:
        return sum(self.opex_tusd_fp_mensal()) + sum(self.opex_te_fp_mensal())

    def opex_p_energia_anual(self) -> float:
        return sum(self.opex_tusd_ponta_mensal()) + sum(self.opex_te_ponta_mensal())

    def opex_fp_demanda_anual(self) -> float:
        return sum(self.opex_demanda_spt_mensal())


# ═══════════════════════════════════════════════════════════════════════
# CALCULADORA DE FLUXO DE CAIXA (módulos 1–8)
# ═══════════════════════════════════════════════════════════════════════

class CalculadoraCF:
    """Gera o Fluxo de Caixa de cada módulo ao longo de anos."""

    def __init__(self, params: ParamsCF):
        self.p = params

    def _fator_reajuste(self, ano: int, taxa: float) -> float:
        return (1 + taxa) ** ano

    def _descontar(self, valor: float, ano: int) -> float:
        if ano == 0:
            return valor
        return valor / (1 + self.p.taxa_desconto) ** ano

    def cf_grid(self, opex_fp_energia: float, opex_p_energia: float,
                opex_fp_demanda: float) -> dict:
        anos = self.p.anos_projeto
        cf = {
            "CAPITAL": [0.0]*(anos+1), "REPLACEMENT": [0.0]*(anos+1),
            "O&M": [0.0]*(anos+1), "OPERATING_FP_ENERGIA": [],
            "OPERATING_P_ENERGIA": [], "OPERATING_FP_DEMANDA": [],
        }
        for a in range(anos+1):
            cf["OPERATING_FP_ENERGIA"].append(
                -opex_fp_energia * self._fator_reajuste(a, self.p.reajuste_tarifa_fp))
            cf["OPERATING_P_ENERGIA"].append(
                -opex_p_energia * self._fator_reajuste(a, self.p.reajuste_tarifa_ponta))
            cf["OPERATING_FP_DEMANDA"].append(
                -opex_fp_demanda * self._fator_reajuste(a, self.p.reajuste_demanda_spt))
        return cf

    def cf_solar_scdee(self, capex: float, om: float, saving_fp_energia: float,
                       custo_troca_inv: float, ano_troca: int) -> dict:
        anos = self.p.anos_projeto
        cf = {
            "CAPITAL": [-capex] + [0.0]*anos,
            "REPLACEMENT": [0.0]*(anos+1),
            "O&M": [-om]*(anos+1),
            "OPERATING_FP_ENERGIA": [saving_fp_energia]*(anos+1),
            "OPERATING_P_ENERGIA": [0.0]*(anos+1),
            "OPERATING_FP_DEMANDA": [0.0]*(anos+1),
        }
        if 0 < ano_troca <= anos:
            cf["REPLACEMENT"][ano_troca] = -custo_troca_inv
        return cf

    def cf_bess_ponta(self, capex: float, custo_reposicao: float, ano_reposicao: int,
                      opex_fp_carga: float, saving_ponta: float) -> dict:
        anos = self.p.anos_projeto
        cf = {
            "CAPITAL": [-capex] + [0.0]*anos,
            "REPLACEMENT": [0.0]*(anos+1),
            "O&M": [0.0]*(anos+1),
            "OPERATING_FP_ENERGIA": [-opex_fp_carga]*(anos+1),
            "OPERATING_P_ENERGIA": [saving_ponta]*(anos+1),
            "OPERATING_FP_DEMANDA": [0.0]*(anos+1),
        }
        if 0 < ano_reposicao <= anos:
            cf["REPLACEMENT"][ano_reposicao] = -custo_reposicao
        return cf

    def cf_gen_ponta(self, capex: float, om: float, vida_util: int,
                     saving_ponta: float) -> dict:
        anos = self.p.anos_projeto
        cf = {
            "CAPITAL": [-capex] + [0.0]*anos,
            "REPLACEMENT": [0.0]*(anos+1),
            "O&M": [-om]*(anos+1),
            "OPERATING_FP_ENERGIA": [0.0]*(anos+1),
            "OPERATING_P_ENERGIA": [saving_ponta]*(anos+1),
            "OPERATING_FP_DEMANDA": [0.0]*(anos+1),
        }
        for a in range(vida_util, anos+1, vida_util):
            cf["REPLACEMENT"][a] = -capex
        return cf

    def totalizar_cf(self, cfs: list[dict]) -> list[float]:
        anos = self.p.anos_projeto
        total = [0.0]*(anos+1)
        for cf in cfs:
            for linha in cf.values():
                for a, v in enumerate(linha):
                    if a <= anos:
                        total[a] += v
        return total

    def descontar_serie(self, serie: list[float]) -> list[float]:
        return [self._descontar(v, a) for a, v in enumerate(serie)]

    def calcular_vpl(self, serie_fc: list[float]) -> float:
        return sum(self.descontar_serie(serie_fc))

    def calcular_tir(self, serie_fc: list[float]) -> Optional[float]:
        def npv(r, s):
            try:
                return sum(v/(1+r)**t for t,v in enumerate(s))
            except (OverflowError, ZeroDivisionError):
                return float('inf')
        def dnpv(r, s):
            try:
                return sum(-t*v/(1+r)**(t+1) for t,v in enumerate(s) if t > 0)
            except (OverflowError, ZeroDivisionError):
                return 0.0
        # Precisamos de ao menos um fluxo positivo para existir TIR
        if not any(v > 0 for v in serie_fc):
            return None
        r = 0.10
        for _ in range(1000):
            f, df = npv(r, serie_fc), dnpv(r, serie_fc)
            if df == 0 or math.isnan(f) or math.isinf(f):
                return None
            r1 = r - f/df
            if abs(r1-r) < 1e-8:
                return r1 if -1 < r1 < 10 else None
            r = r1
            if not (-1 < r < 10):
                return None
        return None

    def calcular_payback(self, serie_fc: list[float]) -> Optional[int]:
        acum = 0.0
        for a, v in enumerate(serie_fc):
            acum += v
            if acum >= 0:
                return a
        return None

    def calcular_roi(self, vpl: float, investimento: float) -> float:
        return 0.0 if investimento == 0 else vpl / abs(investimento)


# ═══════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO SOLARIMÉTRICA (SONDA / PVGIS / TMY)
# ═══════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════
# MOTOR PRINCIPAL — EstudoViabilidade
# ═══════════════════════════════════════════════════════════════════════

class EstudoViabilidade:
    """
    Motor central do estudo de viabilidade híbrida.
    Ordem de execução:
      1.load → 2.grid → 3.solar → 4.bess_ponta → 5.gen_ponta →
      6.gen_form → 7.bess_form → 8.new_grid → 9.cf → 10.summary
      GZ.gridzero (independente, não requer Load)
    """

    def __init__(self, licenca: LicencaModulos):
        self.lic = licenca
        self.load:        Optional[InputLoad]           = None
        self.grid:        Optional[InputGrid]           = None
        self.solar:       Optional[InputSolarSCDEE]     = None
        self.bess_ponta:  Optional[InputBESSPonta]      = None
        self.gen_ponta:   Optional[InputGeradorPonta]   = None
        self.gen_form:    Optional[InputGeradorFormador] = None
        self.bess_form:   Optional[InputBESSFormador]   = None
        self.solar_bess:  Optional[SolarHibridoParams]  = None
        self.solar_gen:   Optional[SolarHibridoParams]  = None
        self.new_grid:    Optional[InputNewGrid]        = None
        self.params_cf:   ParamsCF = ParamsCF()
        self._resultados: dict = {}

    # ── Carregamento ──────────────────────────────────────────────────
    def carregar_load(self, load: InputLoad):
        self.lic.requer("load")
        load.validar()
        self.load = load
        log.info(f"Load carregado: demanda máx = {load.demanda_maxima_kw} kW")

    def carregar_grid(self, grid: InputGrid, buscar_api: bool = False,
                      config_api: Optional[ConfigAPIANEEL] = None):
        self.lic.requer("grid")
        if buscar_api and config_api:
            cliente = ClienteAPIANEEL(config_api)
            dados_api = cliente.buscar_com_fallback(
                grid.concessionaria, grid.subgrupo, grid.modalidade, grid.ano_revisao)
            if dados_api:
                grid = InputGrid.de_api_aneel(dados_api)
                log.info("Tarifas atualizadas via API ANEEL.")
        self.grid = grid
        log.info(f"Grid carregado: {grid.concessionaria}/{grid.subgrupo}/"
                 f"{grid.modalidade}/{grid.ano_revisao}")

    def carregar_solar_scdee(self, solar: InputSolarSCDEE,
                              integrador: Optional[IntegradorSolarimetrico] = None):
        self.lic.requer("solar")
        if integrador and not solar.potencia_gerada_kw:
            solar.potencia_gerada_kw = integrador.gerar_matriz_potencia_12x24()
            solar.potencia_injetada_kw = [[-v for v in l] for l in solar.potencia_gerada_kw]
            solar.fonte_dados = integrador.fonte
        self.solar = solar
        log.info(f"Solar SCDEE: {solar.potencia_cc_kwp} kWp / "
                 f"{solar.modalidade_gd} / {solar.fonte_dados}")

    def carregar_bess_ponta(self, bess: InputBESSPonta):
        self.lic.requer("bess_ponta")
        self.bess_ponta = bess
        log.info(f"BESS Ponta: CAPEX R$ {bess.capex_r:,.0f}")

    def carregar_gen_ponta(self, gen: InputGeradorPonta):
        self.lic.requer("gen_ponta")
        self.gen_ponta = gen

    def carregar_gen_form(self, gen: InputGeradorFormador):
        self.lic.requer("gen_form")
        self.gen_form = gen

    def carregar_bess_form(self, bess: InputBESSFormador):
        self.lic.requer("bess_form")
        self.bess_form = bess

    def carregar_new_grid(self, ng: InputNewGrid):
        self.lic.requer("new_grid")
        ng.grid = ng.grid or self.grid
        self.new_grid = ng

    def configurar_cf(self, params: ParamsCF):
        self.lic.requer("cf")
        self.params_cf = params

    # ── OPEX Grid ─────────────────────────────────────────────────────
    def calcular_opex_grid(self) -> dict:
        assert self.load and self.grid
        calc = CalculadoraOPEXGrid(self.load, self.grid)
        return {
            "mensal": {
                "tusd_ponta": calc.opex_tusd_ponta_mensal(),
                "tusd_fp":    calc.opex_tusd_fp_mensal(),
                "te_ponta":   calc.opex_te_ponta_mensal(),
                "te_fp":      calc.opex_te_fp_mensal(),
                "demanda_spt":calc.opex_demanda_spt_mensal(),
                "total":      calc.opex_grid_total_mensal(),
            },
            "anual": {
                "fp_energia": calc.opex_fp_energia_anual(),
                "p_energia":  calc.opex_p_energia_anual(),
                "fp_demanda": calc.opex_fp_demanda_anual(),
                "total":      calc.opex_grid_anual(),
            },
        }

    # ── OPEX Solar ────────────────────────────────────────────────────
    def calcular_opex_solar(self) -> dict:
        assert self.solar and self.grid
        opex_e = self.solar.calcular_opex_energia_mensal(self.grid)
        opex_d = self.solar.calcular_opex_demanda_mensal(self.grid)
        return {
            "mensal_energia": opex_e, "mensal_demanda": opex_d,
            "anual_energia": sum(opex_e), "anual_demanda": sum(opex_d),
            "capex": self.solar.capex_r, "om": self.solar.om_anual_r,
        }

    # ── Fluxo de Caixa ────────────────────────────────────────────────
    def calcular_cf(self) -> dict:
        self.lic.requer("cf")
        assert self.grid and self.load

        calc        = CalculadoraCF(self.params_cf)
        opex_g      = self.calcular_opex_grid()["anual"]
        cfs         = []
        capex_total = 0.0

        cf_g = calc.cf_grid(opex_g["fp_energia"], opex_g["p_energia"], opex_g["fp_demanda"])
        self._resultados["cf_grid"] = cf_g

        if self.solar and self.lic.solar:
            opex_s = self.calcular_opex_solar()
            cf_s = calc.cf_solar_scdee(
                capex=self.solar.capex_r, om=self.solar.om_anual_r,
                saving_fp_energia=-opex_s["anual_energia"],
                custo_troca_inv=self.solar.custo_troca_inversor_r,
                ano_troca=self.solar.ano_troca_inversor,
            )
            cfs.append(cf_s); capex_total += self.solar.capex_r
            self._resultados["cf_solar"] = cf_s

        if self.bess_ponta and self.lic.bess_ponta:
            opex_carga = self.bess_ponta.calcular_opex_fp_energia(
                self.load.demanda_kw, self.bess_ponta.potencia_max_carga_kw, self.grid)
            saving_p = self.bess_ponta.calcular_saving_ponta(self.load.demanda_kw, self.grid)
            cf_bp = calc.cf_bess_ponta(
                capex=self.bess_ponta.capex_r,
                custo_reposicao=self.bess_ponta.custo_reposicao_r,
                ano_reposicao=self.bess_ponta.tempo_reposicao_anos,
                opex_fp_carga=opex_carga, saving_ponta=saving_p,
            )
            cfs.append(cf_bp); capex_total += self.bess_ponta.capex_r
            self._resultados["cf_bess_ponta"] = cf_bp

        if self.gen_ponta and self.lic.gen_ponta:
            cf_gp = calc.cf_gen_ponta(
                capex=self.gen_ponta.capex_r, om=self.gen_ponta.om_anual_r,
                vida_util=self.gen_ponta.vida_util_anos,
                saving_ponta=opex_g["p_energia"],
            )
            cfs.append(cf_gp); capex_total += self.gen_ponta.capex_r
            self._resultados["cf_gen_ponta"] = cf_gp

        if self.new_grid and self.lic.new_grid:
            cf_ng = {
                "CAPITAL": [-self.new_grid.capex_r] + [0.0]*self.params_cf.anos_projeto,
                "REPLACEMENT": [0.0]*(self.params_cf.anos_projeto+1),
                "O&M": [0.0]*(self.params_cf.anos_projeto+1),
                "OPERATING_FP_ENERGIA": cf_g["OPERATING_FP_ENERGIA"],
                "OPERATING_P_ENERGIA":  cf_g["OPERATING_P_ENERGIA"],
                "OPERATING_FP_DEMANDA": cf_g["OPERATING_FP_DEMANDA"],
            }
            cfs.append(cf_ng); capex_total += self.new_grid.capex_r
            self._resultados["cf_new_grid"] = cf_ng

        baseline     = calc.totalizar_cf([cf_g])
        proposta     = calc.totalizar_cf(cfs) if cfs else [0.0]*(self.params_cf.anos_projeto+1)
        saving_serie = [p - b for p,b in zip(proposta, baseline)]
        fc_total     = [s + b for s,b in zip(saving_serie, baseline)]

        vpl     = calc.calcular_vpl(fc_total)
        tir     = calc.calcular_tir(fc_total)
        payback = calc.calcular_payback(fc_total)
        roi     = calc.calcular_roi(vpl, capex_total)

        resultados = {
            "baseline_nominal": baseline, "proposta_nominal": proposta,
            "saving_serie": saving_serie, "fc_total_nominal": fc_total,
            "fc_total_descontado": calc.descontar_serie(fc_total),
            "vpl": round(vpl, 2),
            "tir": round(tir*100, 4) if tir else None,
            "payback_anos": payback,
            "roi": round(roi, 4),
            "capex_total": capex_total,
            "viavel": tir is not None and tir > self.params_cf.taxa_desconto,
            "indicadores": {
                "taxa_desconto": self.params_cf.taxa_desconto,
                "inflacao": self.params_cf.inflacao,
                "anos_projeto": self.params_cf.anos_projeto,
                "taxa_desconto_real": self.params_cf.taxa_desconto_real,
            },
        }
        self._resultados["cf_consolidado"] = resultados
        return resultados

    # ── GridZero ──────────────────────────────────────────────────────
    def calcular_gridzero(
        self,
        gz: Optional[InputGridZero] = None,
        potencias_kw: Optional[list[float]] = None,
    ) -> dict[float, ResultadoGridZero]:
        """
        Executa análise GridZero.

        Parâmetros
        ----------
        gz : InputGridZero, opcional
            Se não fornecido, cria instância padrão com dados da planilha
            e tarifas do Grid carregado (se disponível).
        potencias_kw : list[float], opcional
            Potências AC a comparar. Padrão: [25, 50, 75, 100, 150] kW.

        Retorna
        -------
        dict {potencia_ac_kw: ResultadoGridZero}
        """
        self.lic.requer("gridzero")

        if gz is None:
            gz = InputGridZero()
            gz.carregar_demanda_horaria_planilha()
            # Herda tarifas do Grid carregado, se disponível
            if self.grid:
                gz.te_kwh   = self.grid.te_fp
                gz.tusd_kwh = self.grid.tusd_fp
                gz.preset_concessionaria = "manual"
                log.info("GridZero: tarifas herdadas do InputGrid carregado.")

        analise  = AnaliseComparativaGridZero(gz, potencias_kw)
        resultados = analise.rodar()
        self._resultados["gridzero"] = {
            str(kw): r.to_dict() for kw, r in resultados.items()
        }
        log.info(f"GridZero calculado para {len(resultados)} tamanhos de sistema.")
        return resultados

    # ── Sumário ───────────────────────────────────────────────────────
    def gerar_summary(self) -> dict:
        self.lic.requer("summary")
        cf    = self._resultados.get("cf_consolidado", {})
        opex_g = self.calcular_opex_grid()["anual"] if self.grid and self.load else {}
        gz_res = self._resultados.get("gridzero", {})

        return {
            "projeto": {
                "concessionaria":    self.grid.concessionaria if self.grid else None,
                "subgrupo":          self.grid.subgrupo if self.grid else None,
                "demanda_maxima_kw": self.load.demanda_maxima_kw if self.load else None,
                "potencia_solar_kwp":self.solar.potencia_cc_kwp if self.solar else None,
                "energia_bess_kwh":  self.bess_ponta.energia_dod80_kwh if self.bess_ponta else None,
            },
            "custos": {
                "opex_grid_anual": opex_g.get("total"),
                "capex_total":     cf.get("capex_total"),
            },
            "indicadores": {
                "vpl":     cf.get("vpl"),
                "tir_pct": cf.get("tir"),
                "payback": cf.get("payback_anos"),
                "roi":     cf.get("roi"),
                "viavel":  cf.get("viavel"),
            },
            "gridzero": gz_res,
            "modulos_ativos": {
                k: getattr(self.lic, k)
                for k in ["load","grid","solar","bess_ponta","gen_ponta",
                          "gen_form","bess_form","new_grid","cf","summary","gridzero"]
            },
        }

    def para_json(self) -> str:
        def _clean(obj):
            if isinstance(obj, float):
                return None if math.isnan(obj) or math.isinf(obj) else obj
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_clean(v) for v in obj]
            return obj
        return json.dumps(_clean(self._resultados), ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# DADOS DE EXEMPLO (planilha original + GridZero)
# ═══════════════════════════════════════════════════════════════════════

def exemplo_planilha_original() -> EstudoViabilidade:
    """Instancia o motor com os dados exatos da planilha de viabilidade."""
    lic = LicencaModulos(
        load=True, grid=True, solar=True, bess_ponta=True,
        gen_ponta=False, gen_form=False, bess_form=False,
        new_grid=False, cf=True, summary=True, gridzero=False,
    )
    estudo = EstudoViabilidade(lic)

    demanda_kw = [
        [16.8,17.64,15.96,16.8,17.64,15.96,15.12,21.0,42.84,51.24,55.44,56.28,63.0,121.8,151.2,151.2,158.76,146.16,123.48,121.8,125.16,33.6,20.16,21.0],
        [36.96,17.64,17.64,16.8,19.32,16.8,21.84,63.84,88.2,95.76,101.64,104.16,140.28,196.56,215.04,215.88,186.48,211.68,111.72,88.2,89.04,77.28,57.96,40.32],
        [19.32,18.48,20.16,20.16,18.48,17.64,40.32,77.28,100.8,105.0,112.56,117.6,151.2,204.12,215.04,225.96,214.2,198.24,133.56,99.12,98.28,92.4,76.44,27.72],
        [15.12,14.28,14.28,13.44,13.44,15.12,21.0,28.56,36.12,72.24,67.2,66.36,94.92,163.8,168.0,152.88,151.2,145.32,73.92,84.0,76.44,63.84,57.12,34.44],
        [16.8,15.96,14.28,15.96,14.28,15.12,18.48,28.56,42.0,46.2,51.24,52.08,63.84,124.32,152.88,143.64,129.36,118.44,78.96,84.0,81.48,61.32,43.68,21.0],
        [17.64,15.96,18.48,16.8,17.64,15.96,21.0,25.2,27.72,29.4,32.76,38.64,48.72,99.96,99.96,93.24,79.8,72.24,36.96,40.32,41.16,36.96,33.6,25.2],
        [13.44,13.44,13.44,13.44,13.44,13.44,17.64,22.68,25.2,26.04,28.56,26.04,37.8,88.2,91.56,79.8,73.92,75.6,25.2,26.88,26.04,25.2,20.16,15.12],
        [16.8,15.12,16.8,15.12,15.12,15.96,22.68,26.88,49.56,46.2,49.56,59.64,64.68,131.88,141.96,136.92,124.32,109.2,51.24,58.8,57.12,52.08,34.44,18.48],
        [21.0,20.16,19.32,19.32,18.48,39.48,41.16,104.16,128.52,141.96,153.72,148.68,186.48,213.36,221.76,192.36,200.76,180.6,137.76,144.48,141.96,129.36,78.96,25.2],
        [67.2,68.88,71.4,64.68,43.68,47.88,38.64,63.84,73.92,79.8,90.72,91.56,149.52,200.76,207.48,199.08,178.92,159.6,106.68,105.84,96.6,83.16,77.28,80.64],
        [24.36,25.2,24.36,24.36,24.36,23.52,27.72,172.2,173.04,91.56,95.76,106.68,171.36,223.44,238.56,226.8,199.08,180.6,110.88,85.68,78.96,71.4,51.24,25.2],
        [51.24,20.16,20.16,19.32,19.32,18.48,34.44,69.72,81.48,93.24,103.32,110.04,150.36,184.8,187.32,183.12,177.24,171.36,104.16,83.16,70.56,67.2,48.72,38.64],
    ]
    estudo.carregar_load(InputLoad(
        demanda_maxima_kw=238.56, demanda_kw=demanda_kw,
        energia_ponta_kwh=[2662.80,5453.28,6108.06,4160.52,4073.58,2931.60,
                           1882.23,4177.74,5302.71,5503.05,5112.45,3932.04],
        energia_fp_kwh=[12627.09,22532.58,25641.63,15337.77,14943.18,11676.42,
                        9338.28,16476.39,21940.80,22099.56,23826.81,18554.55],
    ))

    estudo.carregar_grid(InputGrid(
        concessionaria="Cemig-D", ano_revisao=2023, subgrupo="A4", modalidade="Verde",
        tusd_ponta=1.326, tusd_fp=0.118, te_ponta=0.379, te_fp=0.232,
        tusd_fio_a_p=0.25728, tusd_fio_b_p=1.130074, tusd_tfsee_p=0.000341,
        tusd_pd_p=0.0093775, te_pd_p=0.002728, outros_p=0.305195,
        tusd_tfsee_fp=0.00042, tusd_pd_fp=0.00042, te_pd_fp=0.0028,
        outros_fp=0.34640, demanda_sem_posto=16.54, tusd_fio_a_dem=5.544208,
        tusd_fio_b_dem=13.513180, outros_dem=-2.520696, demanda_geracao=9.45,
        fator_k=4.8714, demanda_contratada_kw=250.488,
    ))

    potencia_gerada = [
        [0,0,0,0,0,0,17.40,65.06,150.22,187.30,215.65,219.45,220.18,216.99,209.59,162.38,108.36,39.44,6.02,0,0,0,0,0],
        [0,0,0,0,0,0,12.77,66.64,136.29,196.90,221.03,223.30,224.44,221.21,213.26,176.20,126.80,44.87,5.02,0,0,0,0,0],
        [0,0,0,0,0,0,4.81,70.49,147.68,211.25,225.17,225.17,225.17,224.88,215.67,180.70,114.55,38.64,2.32,0,0,0,0,0],
        [0,0,0,0,0,0,1.81,80.34,156.23,212.49,224.68,225.17,225.17,223.01,214.13,169.02,98.24,24.52,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,74.52,151.45,208.13,219.57,224.29,225.17,218.80,203.96,155.84,82.20,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,65.62,139.51,194.38,216.23,221.38,221.64,217.09,200.47,150.19,79.81,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,56.85,131.30,187.05,214.32,219.65,220.54,217.10,211.26,154.39,86.22,2.60,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,63.50,132.60,189.21,215.42,221.63,222.97,219.08,208.43,158.62,91.74,5.98,0,0,0,0,0,0],
        [0,0,0,0,0,0,18.02,97.49,176.24,214.25,220.68,222.31,221.81,216.92,198.59,164.14,91.54,14.66,0,0,0,0,0,0],
        [0,0,0,0,0,0,26.92,103.33,182.71,212.45,225.17,221.86,221.05,215.82,193.81,150.22,75.38,14.51,0,0,0,0,0,0],
        [0,0,0,0,0,2.77,25.99,97.08,169.43,213.05,218.78,219.80,218.93,221.46,186.67,134.97,67.19,20.10,0,0,0,0,0,0],
        [0,0,0,0,0,2.83,24.40,89.90,158.65,208.36,216.08,220.18,219.58,214.5,190.86,161.87,96.52,26.92,4.79,0,0,0,0,0],
    ]
    estudo.carregar_solar_scdee(InputSolarSCDEE(
        estado="São Paulo", potencia_ca_kw=211.27, potencia_cc_kwp=300.0,
        sobrecarga_inversor=1.42, capex_r=885000, om_anual_r=1500,
        degradacao_ano1=0.02, degradacao_demais=0.0055,
        custo_troca_inversor_r=50000, ano_troca_inversor=12,
        modalidade_gd="GDIII", data_estudo_ano=2024,
        tusd_ponta=1.326, tusd_fp=0.118, te_ponta=0.379, te_fp=0.232,
        tusd_fio_a_p=0.25728, tusd_fio_b_p=1.130074,
        outros_p=0.305195, demanda_geracao_r=9.45,
        potencia_gerada_kw=potencia_gerada,
        potencia_injetada_kw=[[-v for v in l] for l in potencia_gerada],
        fonte_dados="manual",
    ))

    estudo.carregar_bess_ponta(InputBESSPonta(
        capex_r=5_526_000, custo_reposicao_r=5_526_000,
        tempo_reposicao_anos=14, vida_util_anos=14, percentual_eol=0.60,
        n_ciclos_dod80=4882.5, n_ciclos_dod100=3906, dod_operacional=0.80,
        n_bms_por_br=18, n_bms_total=180, n_brs=10, brs_serie=1, brs_paralelo=10,
        tensao_nominal_v=691.2, capacidade_c10_ah=2890,
        corrente_max_carga_a=330, corrente_max_descarga_a=330,
        potencia_max_carga_kw=228.096, potencia_max_descarga_kw=228.096,
        eta_pcs=0.982, eta_bateria=0.9885, eta_sys=0.99, eta_total=0.961,
        energia_dod80_kwh=1598.05, energia_dod100_kwh=1997.57,
        energia_dod80_pos_pcs=1535.73, energia_dod100_pos_pcs=1919.66,
        tempo_carga_h=7.006, tempo_descarga_h=7.006,
    ))

    estudo.configurar_cf(ParamsCF(
        taxa_desconto=0.08, inflacao=0.0393, anos_projeto=25,
        reajuste_tarifa_ponta=0.01, reajuste_tarifa_fp=0.00,
        reajuste_demanda_spt=0.008,
    ))
    return estudo


def exemplo_gridzero_planilha() -> dict[float, ResultadoGridZero]:
    """
    Executa análise GridZero com os dados reais da planilha
    Estudo_Grid-Zero_2.xlsx e tarifas CPFL Paulista B3 (artigo Canal Solar N°33).

    Retorna dict {potencia_ac_kw: ResultadoGridZero} para comparação
    entre sistemas de 25, 50, 75, 100 e 150 kW AC.
    """
    gz = InputGridZero(
        preset_concessionaria="cpfl_b3",   # CPFL Paulista — Classe B3
        capex_kwp=3000.0,                  # R$/kWp (Tabela 2 do artigo)
        om_pct_capex=1.0,                  # 1% CAPEX/ano
        ipca_pct=4.5,                      # IPCA (Tabela 2 do artigo)
        tma_pct=12.0,                      # TMA 12% (Tabela 1/2 do artigo)
        reajuste_tarifa_pct=5.0,           # reajuste anual da tarifa
        anos_projeto=25,
    )
    gz.carregar_demanda_horaria_planilha()

    analise  = AnaliseComparativaGridZero(gz)
    resultados = analise.rodar()
    analise.imprimir_tabela(resultados)
    return resultados


# ═══════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Motor de Estudo de Viabilidade — Sistema Híbrido + GridZero"
    )
    parser.add_argument("--exemplo",   action="store_true",
                        help="Executar com dados da planilha híbrida original")
    parser.add_argument("--gridzero",  action="store_true",
                        help="Executar análise GridZero (planilha Canal Solar N°33)")
    parser.add_argument("--ambos",     action="store_true",
                        help="Executar análise híbrida + GridZero")
    parser.add_argument("--json",      action="store_true",
                        help="Exportar resultados em JSON")
    parser.add_argument("--csv",       action="store_true",
                        help="Exportar resultados GridZero em CSV")
    args = parser.parse_args()

    # Default: roda tudo se nenhum flag fornecido
    rodar_hibrido  = args.exemplo or args.ambos or not any([args.gridzero])
    rodar_gridzero = args.gridzero or args.ambos or not any([args.exemplo])

    SEP = "=" * 70

    if rodar_hibrido:
        print(SEP)
        print("  MOTOR DE VIABILIDADE — SISTEMA HÍBRIDO")
        print("  Dados: ESTUDO_DE_VIABILIDADE_Híbrido_27-06-2024")
        print(SEP)
        estudo  = exemplo_planilha_original()
        cf      = estudo.calcular_cf()
        summary = estudo.gerar_summary()
        print(f"\n  Concessionária   : {summary['projeto']['concessionaria']}")
        print(f"  Subgrupo / Modal : {summary['projeto']['subgrupo']} / Verde")
        print(f"  Demanda máx.     : {summary['projeto']['demanda_maxima_kw']} kW")
        print(f"  Solar            : {summary['projeto']['potencia_solar_kwp']} kWp")
        print(f"  BESS             : {summary['projeto']['energia_bess_kwh']:,.0f} kWh (DOD 80%)")
        print(f"\n  CAPEX total      : R$ {cf['capex_total']:>14,.2f}")
        print(f"  OPEX Grid/ano    : R$ {summary['custos']['opex_grid_anual']:>14,.2f}")
        print(f"\n  VPL (25 anos)    : R$ {cf['vpl']:>14,.2f}")
        print(f"  TIR              : {cf['tir'] if cf['tir'] else 'PROJETO INVIÁVEL':>14}")
        print(f"  Payback          : {cf['payback_anos'] if cf['payback_anos'] else 'N/A':>14}")
        print(f"  ROI              : {cf['roi']:>14.4f}")
        print(f"  Viável           : {'SIM' if cf['viavel'] else 'NÃO':>14}")
        if args.json:
            print("\n--- JSON HÍBRIDO ---")
            print(estudo.para_json())

    if rodar_gridzero:
        print(f"\n{SEP}")
        print("  MÓDULO GRIDZERO")
        print("  Ref.: Canal Solar N°33 — Thiago Farias (Dez/2025)")
        print("  Dados: Estudo_Grid-Zero_2.xlsx")
        print(SEP)
        gz_resultados = exemplo_gridzero_planilha()

        if args.csv:
            gz_base = InputGridZero(preset_concessionaria="cpfl_b3", capex_kwp=3000.0)
            gz_base.carregar_demanda_horaria_planilha()
            analise = AnaliseComparativaGridZero(gz_base)
            analise.exportar_csv("gridzero_resultados.csv", gz_resultados)
            print("CSV exportado: gridzero_resultados.csv")

        if args.json:
            import json as _json
            print("\n--- JSON GRIDZERO ---")
            print(_json.dumps(
                {str(k): v.to_dict() for k, v in gz_resultados.items()},
                ensure_ascii=False, indent=2
            ))
