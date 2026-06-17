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

Dependências:
  pip install numpy pandas requests msal python-dateutil

Uso:
  from motor_viabilidade import EstudoViabilidade, LicencaModulos
  licenca = LicencaModulos(load=True, grid=True, solar=True, bess_ponta=True, cf=True)
  estudo  = EstudoViabilidade(licenca)
  estudo.carregar_load(demanda_matrix, energia_ponta, energia_fp)
  estudo.carregar_grid(params_grid)
  estudo.carregar_solar_scdee(params_solar, potencia_gerada_matrix)
  estudo.carregar_bess_ponta(params_bess)
  resultado = estudo.calcular_cf(taxa_desconto=0.08, inflacao=0.0393, anos=25)
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
    load:       bool = True   # Módulo 1 — Carga
    grid:       bool = True   # Módulo 2 — Tarifa/Grid
    solar:      bool = False  # Módulo 3 — Solar SCDEE
    bess_ponta: bool = False  # Módulo 4 — BESS Ponta
    gen_ponta:  bool = False  # Módulo 5 — Gerador Ponta
    gen_form:   bool = False  # Módulo 6 — Gerador Formador
    bess_form:  bool = False  # Módulo 7 — BESS Formador
    new_grid:   bool = False  # Módulo 8 — Nova Rede
    cf:         bool = True   # Módulo 9 — Fluxo de Caixa (requer grid)
    summary:    bool = True   # Módulo 10 — Sumário

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
    # Endpoint OData do Dataverse ANEEL
    base_url:      str = "https://csisolarcrmprod.crm16.dynamics.com"
    api_version:   str = "v9.2"
    # ID do registro de tarifas (da URL original)
    order_id:      str = "ad670927-b765-f111-ab0c-002248e570e3"
    # Usar cache local (fallback quando API indisponível)
    usar_cache:    bool = True
    cache_path:    str = "aneel_tarifas_cache.json"


class ClienteAPIANEEL:
    """
    Cliente para buscar tarifas diretamente do BI da ANEEL
    (Microsoft Dynamics 365 / Dataverse OData v4).

    Fluxo de autenticação:
      1. MSAL acquires token via client_credentials flow
      2. Bearer token usado em cada requisição OData
      3. Cache local JSON como fallback
    """

    def __init__(self, config: ConfigAPIANEEL):
        self.cfg = config
        self._token: Optional[str] = None

    def _obter_token(self) -> str:
        """Obtém access token via MSAL (client credentials)."""
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
            raise ImportError(
                "Instale msal: pip install msal\n"
                "Necessário para autenticação com a API ANEEL."
            )

    def buscar_tarifa_por_id(self, order_id: str = None) -> dict:
        """
        Busca registro de tarifa no Dataverse pelo ID do pedido.

        Retorna dict com campos de tarifa TUSD/TE por posto tarifário.
        """
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
        self,
        concessionaria: str,
        subgrupo: str,
        modalidade: str,
        ano_revisao: int,
    ) -> dict:
        """
        Consulta OData filtrada por concessionária, subgrupo e modalidade.

        Exemplo de query gerada:
          .../csi_orders?$filter=csi_concessionaria eq 'Cemig-D'
              and csi_subgrupo eq 'A4'
              and csi_modalidade eq 'Verde'
              and csi_ano_revisao eq 2023
          &$select=csi_tusd_ponta,csi_tusd_fp,csi_te_ponta,csi_te_fp,...
        """
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
            "OData-MaxVersion": "4.0", "OData-Version": "4.0",
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
        self,
        concessionaria: str,
        subgrupo: str,
        modalidade: str,
        ano_revisao: int,
    ) -> dict:
        """
        Tenta buscar da API. Se falhar, usa cache local.
        Se cache também falhar, retorna aviso com valores zerados.
        """
        import requests
        chave = f"{concessionaria}__{subgrupo}__{modalidade}__{ano_revisao}"

        # Tentar API
        try:
            dados = self.buscar_tarifas_por_concessionaria(
                concessionaria, subgrupo, modalidade, ano_revisao
            )
            # Salvar no cache
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

        # Fallback: cache local
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

        log.error(
            "API ANEEL e cache local indisponíveis. "
            "Preencha as tarifas manualmente via InputGrid."
        )
        return {}


# ═══════════════════════════════════════════════════════════════════════
# DATA CLASSES — parâmetros de entrada de cada módulo
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class InputLoad:
    """Módulo 1 — Memória de massa de demanda e energia."""
    demanda_maxima_kw: float = 238.56

    # Matrizes 12×24 (meses × horas) — kW
    demanda_kw: list[list[float]] = field(default_factory=list)
    # Energia por posto tarifário — listas de 12 meses
    energia_ponta_kwh:   list[float] = field(default_factory=list)
    energia_fp_kwh:      list[float] = field(default_factory=list)

    def validar(self):
        assert len(self.demanda_kw) == 12, "demanda_kw deve ter 12 meses"
        for i, linha in enumerate(self.demanda_kw):
            assert len(linha) == 24, f"demanda_kw[{i}] deve ter 24 horas"
        assert len(self.energia_ponta_kwh) == 12
        assert len(self.energia_fp_kwh) == 12

    @property
    def energia_equivalente_kwh(self) -> list[float]:
        return [p + fp for p, fp in
                zip(self.energia_ponta_kwh, self.energia_fp_kwh)]

    @property
    def energia_ponta_total(self) -> float:
        return sum(self.energia_ponta_kwh)

    @property
    def energia_fp_total(self) -> float:
        return sum(self.energia_fp_kwh)


@dataclass
class InputGrid:
    """Módulo 2 — Tarifas e encargos da concessionária."""
    concessionaria:       str   = "Cemig-D"
    ano_revisao:          int   = 2023
    subgrupo:             str   = "A4"
    modalidade:           str   = "Verde"

    # R$/kWh
    tusd_ponta:           float = 1.326
    tusd_fp:              float = 0.118
    te_ponta:             float = 0.379
    te_fp:                float = 0.232

    # Componentes tarifários — ponta
    tusd_fio_a_p:         float = 0.25728
    tusd_fio_b_p:         float = 1.130074
    tusd_tfsee_p:         float = 0.000341
    tusd_pd_p:            float = 0.0093775
    te_pd_p:              float = 0.0027280
    outros_p:             float = 0.305195

    # Componentes tarifários — fora ponta
    tusd_fio_a_fp:        float = 0.0
    tusd_fio_b_fp:        float = 0.0
    tusd_tfsee_fp:        float = 0.00042
    tusd_pd_fp:           float = 0.00042
    te_pd_fp:             float = 0.0028
    outros_fp:            float = 0.34640

    # R$/kW
    demanda_sem_posto:    float = 16.54
    tusd_fio_a_dem:       float = 5.544208
    tusd_fio_b_dem:       float = 13.513180
    outros_dem:           float = -2.520696

    demanda_geracao:      float = 9.45
    fator_k:              float = 4.8714
    demanda_contratada_kw:float = 250.488

    @property
    def tarifa_ponta(self) -> float:
        return self.tusd_ponta + self.te_ponta

    @property
    def tarifa_fp(self) -> float:
        return self.tusd_fp + self.te_fp

    @classmethod
    def de_api_aneel(cls, dados_api: dict) -> "InputGrid":
        """Constrói InputGrid a partir de resposta da API ANEEL."""
        g = cls()
        mapa = {
            "csi_tusd_ponta":       "tusd_ponta",
            "csi_tusd_fp":          "tusd_fp",
            "csi_te_ponta":         "te_ponta",
            "csi_te_fp":            "te_fp",
            "csi_demanda_sem_posto":"demanda_sem_posto",
            "csi_demanda_geracao":  "demanda_geracao",
            "csi_tusd_fio_a_p":     "tusd_fio_a_p",
            "csi_tusd_fio_b_p":     "tusd_fio_b_p",
            "csi_fator_k":          "fator_k",
            "csi_outros_p":         "outros_p",
            "csi_outros_fp":        "outros_fp",
        }
        for api_key, attr in mapa.items():
            if api_key in dados_api and dados_api[api_key] is not None:
                setattr(g, attr, float(dados_api[api_key]))
        return g


@dataclass
class InputSolarSCDEE:
    """Módulo 3 — Sistema solar GD / compensação de energia elétrica."""
    estado:             str   = "São Paulo"
    potencia_ca_kw:     float = 211.27
    potencia_cc_kwp:    float = 300.0
    sobrecarga_inversor:float = 1.42
    capex_r:            float = 885000.0
    om_anual_r:         float = 1500.0
    degradacao_ano1:    float = 0.02
    degradacao_demais:  float = 0.0055
    custo_troca_inversor_r: float = 50000.0
    ano_troca_inversor: int   = 12
    modalidade_gd:      str   = "GDIII"   # GDII ou GDIII
    data_estudo_ano:    int   = 2024

    # Cronograma de transição SCDEE (Lei 14.300/2022)
    cronograma_transicao: dict = field(default_factory=lambda: {
        2023: 0.15, 2024: 0.30, 2025: 0.45, 2026: 0.60,
        2027: 0.75, 2028: 0.90,
    })

    # Tarifas para cálculo da economia SCDEE (herda do Grid)
    tusd_ponta:         float = 1.326
    tusd_fp:            float = 0.118
    te_ponta:           float = 0.379
    te_fp:              float = 0.232
    tusd_fio_a_p:       float = 0.25728
    tusd_fio_b_p:       float = 1.130074
    outros_p:           float = 0.305195
    demanda_geracao_r:  float = 9.45

    # Potência gerada — matriz 12×24 (kW AC)
    potencia_gerada_kw: list[list[float]] = field(default_factory=list)
    # Potência injetada na barra — matriz 12×24 (negativa = injeção)
    potencia_injetada_kw: list[list[float]] = field(default_factory=list)

    # Dados integrados dos módulos solarimétricos
    fonte_dados: str = "manual"  # "sonda" | "pvgis" | "tmy" | "manual"
    dados_sonda: dict = field(default_factory=dict)
    dados_pvgis: dict = field(default_factory=dict)
    dados_tmy:   dict = field(default_factory=dict)

    @property
    def periodo_transicao_vigente(self) -> float:
        ano = self.data_estudo_ano
        for a in sorted(self.cronograma_transicao.keys(), reverse=True):
            if ano >= a:
                return self.cronograma_transicao[a]
        return 0.0

    def energia_injetada_mensal_kwh(self) -> list[float]:
        """Energia injetada na barra por mês (kWh), integração horária."""
        resultado = []
        for m in range(12):
            if m < len(self.potencia_injetada_kw):
                resultado.append(abs(sum(self.potencia_injetada_kw[m])))
            else:
                resultado.append(0.0)
        return resultado

    def energia_gerada_mensal_kwh(self) -> list[float]:
        resultado = []
        for m in range(12):
            if m < len(self.potencia_gerada_kw):
                resultado.append(sum(self.potencia_gerada_kw[m]))
            else:
                resultado.append(0.0)
        return resultado

    def calcular_opex_energia_mensal(self, grid: InputGrid) -> list[float]:
        """
        OPEX Solar SCDEE — Energia: economia gerada pela compensação GD.
        Considera modalidade GDII ou GDIII e cronograma de transição.
        """
        result = []
        energia_inj = self.energia_injetada_mensal_kwh()
        ft = self.periodo_transicao_vigente

        for m in range(12):
            e = energia_inj[m]
            if self.modalidade_gd == "GDIII":
                # GDIII: crédito = TUSD(FIO A) + TUSD TFSEE + TUSD P&D + Outros
                credito_kwh = (grid.tusd_fio_a_p + grid.tusd_tfsee_p
                               + grid.tusd_pd_p + grid.outros_fp)
            else:
                # GDII: crédito = TUSD(FIO B)
                credito_kwh = grid.tusd_fio_b_p

            # Economia = injeção × (tarifa FP − desconto transição × FIO B)
            economia = e * (grid.te_fp + grid.tusd_fp
                            - ft * grid.tusd_fio_b_fp)
            result.append(-economia)  # negativo = redução de custo
        return result

    def calcular_opex_demanda_mensal(self, grid: InputGrid) -> list[float]:
        """Redução de demanda de geração pelo solar."""
        dem_red = self.potencia_ca_kw * grid.demanda_geracao_r / 12
        return [-dem_red] * 12


@dataclass
class InputBESSPonta:
    """Módulo 4 — Bateria para redução de ponta."""
    capex_r:                float = 5_526_000.0
    custo_reposicao_r:      float = 5_526_000.0
    tempo_reposicao_anos:   int   = 14
    vida_util_anos:         int   = 14
    percentual_eol:         float = 0.60
    n_ciclos_dod80:         float = 4882.5
    n_ciclos_dod100:        float = 3906.0
    dod_operacional:        float = 0.80

    # Sistema
    n_bms_por_br:           int   = 18
    n_bms_total:            int   = 180
    n_brs:                  int   = 10
    brs_serie:              int   = 1
    brs_paralelo:           int   = 10

    # Parâmetros elétricos
    tensao_nominal_v:       float = 691.2
    resistencia_interna_mohm:float= 43.2
    coulombic_eff:          float = 0.953
    tensao_corte_carga_v:   float = 777.6
    tensao_corte_descarga_v:float = 583.2
    capacidade_c10_ah:      float = 2890.0
    corrente_max_carga_a:   float = 330.0
    corrente_max_descarga_a:float = 330.0
    potencia_max_carga_kw:  float = 228.096
    potencia_max_descarga_kw:float= 228.096

    # Eficiências
    perda_sistema:          float = 0.0115
    eta_pcs:                float = 0.982
    eta_bateria:            float = 0.9885
    eta_sys:                float = 0.99
    eta_total:              float = 0.961

    # Energia armazenada
    energia_dod80_kwh:      float = 1598.05
    energia_dod100_kwh:     float = 1997.57
    energia_dod80_pos_pcs:  float = 1535.73
    energia_dod100_pos_pcs: float = 1919.66

    # Tempo de carga/descarga
    tempo_carga_h:          float = 7.006
    tempo_descarga_h:       float = 7.006

    def energia_eol_dod80_kwh(self) -> float:
        return self.energia_dod80_kwh * self.percentual_eol

    def calcular_opex_fp_energia(
        self,
        demanda_kw: list[list[float]],
        potencia_max_kw: float,
        grid: InputGrid
    ) -> float:
        """
        Custo de carga do BESS fora-ponta (energia consumida para carregar).
        """
        total = 0.0
        for m in range(12):
            energia_carga = potencia_max_kw * self.tempo_carga_h / self.eta_total
            total += energia_carga * grid.tarifa_fp
        return total

    def calcular_saving_ponta(
        self,
        demanda_kw: list[list[float]],
        grid: InputGrid
    ) -> float:
        """
        Saving em ponta: o BESS abate a demanda de ponta,
        reduzindo o custo de TUSD Ponta + TE Ponta.
        """
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
    consumo_min_lh:     float = 0.0   # litros/hora no mínimo
    consumo_max_lh:     float = 0.0
    custo_diesel_litro: float = 5.92
    coef_interceptacao: float = 0.0
    slope:              float = 0.0

    def custo_diesel_kwh(self) -> float:
        if self.consumo_max_lh > 0 and self.potencia_kw > 0:
            return (self.consumo_max_lh * self.custo_diesel_litro
                    / self.potencia_kw)
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
    capex_r:                float = 5_560_000.0
    custo_reposicao_r:      float = 5_560_000.0
    tempo_reposicao_anos:   int   = 14
    vida_util_anos:         int   = 14
    energia_dod80_kwh:      float = 0.0
    eta_total:              float = 0.961


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
        total = 0.0
        for m in range(12):
            if m < len(self.potencia_gerada_kw):
                total += sum(self.potencia_gerada_kw[m])
        return total


@dataclass
class InputNewGrid:
    """Módulo 8 — Custo de implantação de nova rede elétrica."""
    capex_r: float = 15_000_000.0
    # Tarifas idênticas ao Grid existente
    grid: Optional[InputGrid] = None


@dataclass
class ParamsCF:
    """Parâmetros econômico-financeiros do fluxo de caixa."""
    taxa_desconto:          float = 0.08    # Discount rate (real)
    inflacao:               float = 0.0393  # Inflation rate (acumulado 12m)
    anos_projeto:           int   = 25
    # Taxa de desconto real = (1+nominal)/(1+inflacao) - 1
    reajuste_tarifa_ponta:  float = 0.010
    reajuste_tarifa_fp:     float = 0.000
    reajuste_demanda_spt:   float = 0.008
    reajuste_combustivel:   float = 0.010

    @property
    def taxa_desconto_real(self) -> float:
        return ((1 + self.taxa_desconto) / (1 + self.inflacao)) - 1


# ═══════════════════════════════════════════════════════════════════════
# CALCULADORA DE OPEX GRID
# ═══════════════════════════════════════════════════════════════════════

class CalculadoraOPEXGrid:
    """
    Calcula o OPEX mensal/anual da tarifa de rede (baseline).
    Fiel à planilha Input - Grid.
    """

    def __init__(self, load: InputLoad, grid: InputGrid):
        self.load = load
        self.grid = grid

    def opex_tusd_ponta_mensal(self) -> list[float]:
        return [e * self.grid.tusd_ponta
                for e in self.load.energia_ponta_kwh]

    def opex_tusd_fp_mensal(self) -> list[float]:
        return [e * self.grid.tusd_fp
                for e in self.load.energia_fp_kwh]

    def opex_te_ponta_mensal(self) -> list[float]:
        return [e * self.grid.te_ponta
                for e in self.load.energia_ponta_kwh]

    def opex_te_fp_mensal(self) -> list[float]:
        return [e * self.grid.te_fp
                for e in self.load.energia_fp_kwh]

    def opex_demanda_spt_mensal(self) -> list[float]:
        dem_mensal = self.load.demanda_maxima_kw * self.grid.demanda_sem_posto
        return [dem_mensal] * 12

    def opex_grid_total_mensal(self) -> list[float]:
        t_p  = self.opex_tusd_ponta_mensal()
        t_fp = self.opex_tusd_fp_mensal()
        te_p = self.opex_te_ponta_mensal()
        te_fp= self.opex_te_fp_mensal()
        dem  = self.opex_demanda_spt_mensal()
        return [a+b+c+d+e
                for a,b,c,d,e in zip(t_p, t_fp, te_p, te_fp, dem)]

    def opex_grid_anual(self) -> float:
        return sum(self.opex_grid_total_mensal())

    def opex_fp_energia_anual(self) -> float:
        return sum(self.opex_tusd_fp_mensal()) + sum(self.opex_te_fp_mensal())

    def opex_p_energia_anual(self) -> float:
        return sum(self.opex_tusd_ponta_mensal()) + sum(self.opex_te_ponta_mensal())

    def opex_fp_demanda_anual(self) -> float:
        return sum(self.opex_demanda_spt_mensal())


# ═══════════════════════════════════════════════════════════════════════
# CALCULADORA DE FLUXO DE CAIXA
# ═══════════════════════════════════════════════════════════════════════

class CalculadoraCF:
    """
    Gera o Fluxo de Caixa de cada módulo ao longo de `anos` anos.
    Fiel à estrutura das abas CF-BD e CF da planilha.
    """

    def __init__(self, params: ParamsCF):
        self.p = params

    def _fator_reajuste(self, ano: int, taxa: float) -> float:
        return (1 + taxa) ** ano

    def _descontar(self, valor: float, ano: int) -> float:
        if ano == 0:
            return valor
        return valor / (1 + self.p.taxa_desconto) ** ano

    # ── GRID baseline ─────────────────────────────────────────────────
    def cf_grid(
        self,
        opex_fp_energia: float,
        opex_p_energia:  float,
        opex_fp_demanda: float,
    ) -> dict:
        anos = self.p.anos_projeto
        cf = {"CAPITAL": [0.0] * (anos + 1),
              "REPLACEMENT": [0.0] * (anos + 1),
              "O&M":  [0.0] * (anos + 1),
              "OPERATING_FP_ENERGIA": [],
              "OPERATING_P_ENERGIA":  [],
              "OPERATING_FP_DEMANDA": []}

        for a in range(anos + 1):
            cf["OPERATING_FP_ENERGIA"].append(
                -opex_fp_energia * self._fator_reajuste(a, self.p.reajuste_tarifa_fp)
            )
            cf["OPERATING_P_ENERGIA"].append(
                -opex_p_energia * self._fator_reajuste(a, self.p.reajuste_tarifa_ponta)
            )
            cf["OPERATING_FP_DEMANDA"].append(
                -opex_fp_demanda * self._fator_reajuste(a, self.p.reajuste_demanda_spt)
            )
        return cf

    # ── Solar SCDEE ───────────────────────────────────────────────────
    def cf_solar_scdee(
        self,
        capex: float,
        om: float,
        saving_fp_energia: float,
        custo_troca_inv: float,
        ano_troca: int,
    ) -> dict:
        anos = self.p.anos_projeto
        cf = {"CAPITAL": [-capex] + [0.0] * anos,
              "REPLACEMENT": [0.0] * (anos + 1),
              "O&M":  [-om] * (anos + 1),
              "OPERATING_FP_ENERGIA": [saving_fp_energia] * (anos + 1),
              "OPERATING_P_ENERGIA":  [0.0] * (anos + 1),
              "OPERATING_FP_DEMANDA": [0.0] * (anos + 1)}
        if 0 < ano_troca <= anos:
            cf["REPLACEMENT"][ano_troca] = -custo_troca_inv
        return cf

    # ── BESS Ponta ────────────────────────────────────────────────────
    def cf_bess_ponta(
        self,
        capex: float,
        custo_reposicao: float,
        ano_reposicao: int,
        opex_fp_carga: float,
        saving_ponta: float,
    ) -> dict:
        anos = self.p.anos_projeto
        cf = {"CAPITAL": [-capex] + [0.0] * anos,
              "REPLACEMENT": [0.0] * (anos + 1),
              "O&M":  [0.0] * (anos + 1),
              "OPERATING_FP_ENERGIA": [-opex_fp_carga] * (anos + 1),
              "OPERATING_P_ENERGIA":  [saving_ponta] * (anos + 1),
              "OPERATING_FP_DEMANDA": [0.0] * (anos + 1)}
        if 0 < ano_reposicao <= anos:
            cf["REPLACEMENT"][ano_reposicao] = -custo_reposicao
        return cf

    # ── Gerador de Ponta ──────────────────────────────────────────────
    def cf_gen_ponta(
        self,
        capex: float,
        om: float,
        vida_util: int,
        saving_ponta: float,
    ) -> dict:
        anos = self.p.anos_projeto
        cf = {"CAPITAL": [-capex] + [0.0] * anos,
              "REPLACEMENT": [0.0] * (anos + 1),
              "O&M":  [-om] * (anos + 1),
              "OPERATING_FP_ENERGIA": [0.0] * (anos + 1),
              "OPERATING_P_ENERGIA":  [saving_ponta] * (anos + 1),
              "OPERATING_FP_DEMANDA": [0.0] * (anos + 1)}
        for a in range(vida_util, anos + 1, vida_util):
            cf["REPLACEMENT"][a] = -capex
        return cf

    # ── Consolidação ──────────────────────────────────────────────────
    def totalizar_cf(self, cfs: list[dict]) -> list[float]:
        """Soma todas as linhas de CF ao longo do tempo."""
        anos = self.p.anos_projeto
        total = [0.0] * (anos + 1)
        for cf in cfs:
            for linha in cf.values():
                for a, v in enumerate(linha):
                    if a <= anos:
                        total[a] += v
        return total

    def descontar_serie(self, serie: list[float]) -> list[float]:
        return [self._descontar(v, a) for a, v in enumerate(serie)]

    # ── Indicadores ───────────────────────────────────────────────────
    def calcular_vpl(self, serie_fc: list[float]) -> float:
        """VPL da série de FC descontada."""
        return sum(self.descontar_serie(serie_fc))

    def calcular_tir(self, serie_fc: list[float]) -> Optional[float]:
        """TIR via método de Newton-Raphson (até 1000 iterações)."""
        def npv(r, serie):
            return sum(v / (1 + r) ** t for t, v in enumerate(serie))
        def dnpv(r, serie):
            return sum(-t * v / (1 + r) ** (t + 1)
                       for t, v in enumerate(serie) if t > 0)
        r = 0.10
        for _ in range(1000):
            f  = npv(r, serie_fc)
            df = dnpv(r, serie_fc)
            if df == 0:
                return None
            r1 = r - f / df
            if abs(r1 - r) < 1e-8:
                return r1 if -1 < r1 < 10 else None
            r = r1
        return None

    def calcular_payback(self, serie_fc: list[float]) -> Optional[int]:
        """Payback simples: primeiro ano com FC acumulado >= 0."""
        acum = 0.0
        for a, v in enumerate(serie_fc):
            acum += v
            if acum >= 0:
                return a
        return None

    def calcular_roi(self, vpl: float, investimento: float) -> float:
        if investimento == 0:
            return 0.0
        return vpl / abs(investimento)


# ═══════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM MÓDULOS SOLARIMÉTRICOS (SONDA / PVGIS / TMY)
# ═══════════════════════════════════════════════════════════════════════

class IntegradorSolarimetrico:
    """
    Integra os três motores solarimétricos existentes:
      - sonda_collector.py  → dados medidos em campo (Rede SONDA)
      - pvgis_collector.py  → dados de reanálise/satélite (PVGIS 5.2)
      - tmy_generator.py    → Ano Meteorológico Típico (ISO 15927-4)

    O resultado é uma matriz 12×24 de potência solar (kW AC),
    compatível com InputSolarSCDEE.potencia_gerada_kw.
    """

    def __init__(
        self,
        potencia_kwp: float,
        lat: float, lon: float,
        fonte: str = "tmy",       # "sonda" | "pvgis" | "tmy" | "manual"
        station: str = "BRB",     # código SONDA (se fonte="sonda")
        performance_ratio: float = 0.78,
        eta_inversor: float = 0.98,
    ):
        self.kwp = potencia_kwp
        self.lat = lat
        self.lon = lon
        self.fonte = fonte
        self.station = station
        self.pr = performance_ratio
        self.eta_inv = eta_inversor

    def obter_irradiancia_horaria(self) -> dict:
        """
        Retorna dict com DataFrames de irradiância horária
        conforme a fonte configurada.
        """
        if self.fonte == "sonda":
            return self._obter_sonda()
        elif self.fonte == "pvgis":
            return self._obter_pvgis()
        elif self.fonte == "tmy":
            return self._obter_tmy()
        else:
            return {}

    def _obter_sonda(self) -> dict:
        try:
            from sonda_collector import coletar_sonda, SondaConfig
            dados = coletar_sonda(
                station=self.station,
                salvar_raw=False,
                salvar_horario=True,
                salvar_diario=False,
            )
            return {"horario": dados.get("horario")}
        except ImportError:
            log.warning("sonda_collector não encontrado.")
            return {}

    def _obter_pvgis(self) -> dict:
        try:
            from pvgis_collector import obter_serie_horaria, LocalizacaoPV
            local = LocalizacaoPV(lat=self.lat, lon=self.lon)
            df = obter_serie_horaria(local)
            return {"horario": df}
        except ImportError:
            log.warning("pvgis_collector não encontrado.")
            return {}

    def _obter_tmy(self) -> dict:
        try:
            from tmy_generator import tmy_de_pvgis, ConfigTMY
            config = ConfigTMY(lat=self.lat, lon=self.lon)
            resultado = tmy_de_pvgis(
                lat=self.lat, lon=self.lon,
                config=config,
                dir_saida="./tmy_cache",
                formatos=["parquet"],
            )
            return {"tmy": resultado.tmy}
        except ImportError:
            log.warning("tmy_generator não encontrado.")
            return {}

    def gerar_matriz_potencia_12x24(self) -> list[list[float]]:
        """
        Converte série horária de GHI → potência AC 12×24 (kW).
        Modelo simples: P_ac = GHI × (kwp / 1000) × PR × eta_inv
        """
        dados = self.obter_irradiancia_horaria()
        df = dados.get("tmy") or dados.get("horario")

        if df is None or df.empty if hasattr(df, "empty") else not df:
            log.warning("Dados solarimétricos não disponíveis. "
                        "Retornando matriz zerada.")
            return [[0.0] * 24 for _ in range(12)]

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

    Cada módulo é opcional e controlado por LicencaModulos.
    A ordem de execução segue a estrutura de abas da planilha original:
      1. load → 2. grid → 3. solar → 4. bess_ponta →
      5. gen_ponta → 6. gen_form → 7. bess_form → 8. new_grid →
      9. cf → 10. summary
    """

    def __init__(self, licenca: LicencaModulos):
        self.lic = licenca
        # Inputs
        self.load:        Optional[InputLoad]         = None
        self.grid:        Optional[InputGrid]         = None
        self.solar:       Optional[InputSolarSCDEE]   = None
        self.bess_ponta:  Optional[InputBESSPonta]    = None
        self.gen_ponta:   Optional[InputGeradorPonta] = None
        self.gen_form:    Optional[InputGeradorFormador]= None
        self.bess_form:   Optional[InputBESSFormador] = None
        self.solar_bess:  Optional[SolarHibridoParams]= None
        self.solar_gen:   Optional[SolarHibridoParams]= None
        self.new_grid:    Optional[InputNewGrid]      = None
        self.params_cf:   ParamsCF = ParamsCF()
        # Resultados
        self._resultados: dict = {}

    # ── Carregamento de dados ─────────────────────────────────────────
    def carregar_load(self, load: InputLoad):
        self.lic.requer("load")
        load.validar()
        self.load = load
        log.info(f"Load carregado: demanda máx = {load.demanda_maxima_kw} kW")

    def carregar_grid(
        self,
        grid: InputGrid,
        buscar_api: bool = False,
        config_api: Optional[ConfigAPIANEEL] = None,
    ):
        self.lic.requer("grid")
        if buscar_api and config_api:
            cliente = ClienteAPIANEEL(config_api)
            dados_api = cliente.buscar_com_fallback(
                grid.concessionaria, grid.subgrupo,
                grid.modalidade, grid.ano_revisao
            )
            if dados_api:
                grid = InputGrid.de_api_aneel(dados_api)
                # Preservar campos não mapeados via API
                log.info("Tarifas atualizadas via API ANEEL.")
        self.grid = grid
        log.info(f"Grid carregado: {grid.concessionaria} / "
                 f"{grid.subgrupo} / {grid.modalidade} / {grid.ano_revisao}")

    def carregar_solar_scdee(
        self,
        solar: InputSolarSCDEE,
        integrador: Optional[IntegradorSolarimetrico] = None,
    ):
        self.lic.requer("solar")
        if integrador and not solar.potencia_gerada_kw:
            solar.potencia_gerada_kw = integrador.gerar_matriz_potencia_12x24()
            solar.potencia_injetada_kw = [
                [-v for v in linha] for linha in solar.potencia_gerada_kw
            ]
            solar.fonte_dados = integrador.fonte
        self.solar = solar
        log.info(f"Solar SCDEE carregado: {solar.potencia_cc_kwp} kWp / "
                 f"{solar.modalidade_gd} / fonte={solar.fonte_dados}")

    def carregar_bess_ponta(self, bess: InputBESSPonta):
        self.lic.requer("bess_ponta")
        self.bess_ponta = bess
        log.info(f"BESS Ponta carregado: CAPEX R$ {bess.capex_r:,.0f}")

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

    # ── Cálculo OPEX Grid ─────────────────────────────────────────────
    def calcular_opex_grid(self) -> dict:
        assert self.load and self.grid, "Módulos Load e Grid requeridos."
        calc = CalculadoraOPEXGrid(self.load, self.grid)
        return {
            "mensal": {
                "tusd_ponta":  calc.opex_tusd_ponta_mensal(),
                "tusd_fp":     calc.opex_tusd_fp_mensal(),
                "te_ponta":    calc.opex_te_ponta_mensal(),
                "te_fp":       calc.opex_te_fp_mensal(),
                "demanda_spt": calc.opex_demanda_spt_mensal(),
                "total":       calc.opex_grid_total_mensal(),
            },
            "anual": {
                "fp_energia":  calc.opex_fp_energia_anual(),
                "p_energia":   calc.opex_p_energia_anual(),
                "fp_demanda":  calc.opex_fp_demanda_anual(),
                "total":       calc.opex_grid_anual(),
            },
        }

    # ── Cálculo OPEX Solar SCDEE ──────────────────────────────────────
    def calcular_opex_solar(self) -> dict:
        assert self.solar and self.grid
        opex_e = self.solar.calcular_opex_energia_mensal(self.grid)
        opex_d = self.solar.calcular_opex_demanda_mensal(self.grid)
        return {
            "mensal_energia":  opex_e,
            "mensal_demanda":  opex_d,
            "anual_energia":   sum(opex_e),
            "anual_demanda":   sum(opex_d),
            "capex":           self.solar.capex_r,
            "om":              self.solar.om_anual_r,
        }

    # ── Fluxo de Caixa ────────────────────────────────────────────────
    def calcular_cf(self) -> dict:
        self.lic.requer("cf")
        assert self.grid and self.load

        calc  = CalculadoraCF(self.params_cf)
        opex_g= self.calcular_opex_grid()["anual"]
        cfs   = []
        capex_total = 0.0

        # --- Baseline GRID ---
        cf_g = calc.cf_grid(
            opex_fp_energia = opex_g["fp_energia"],
            opex_p_energia  = opex_g["p_energia"],
            opex_fp_demanda = opex_g["fp_demanda"],
        )
        self._resultados["cf_grid"] = cf_g

        # --- Solar SCDEE ---
        cf_s = None
        if self.solar and self.lic.solar:
            opex_s = self.calcular_opex_solar()
            cf_s = calc.cf_solar_scdee(
                capex            = self.solar.capex_r,
                om               = self.solar.om_anual_r,
                saving_fp_energia= -opex_s["anual_energia"],
                custo_troca_inv  = self.solar.custo_troca_inversor_r,
                ano_troca        = self.solar.ano_troca_inversor,
            )
            cfs.append(cf_s)
            capex_total += self.solar.capex_r
            self._resultados["cf_solar"] = cf_s

        # --- BESS Ponta ---
        cf_bp = None
        if self.bess_ponta and self.lic.bess_ponta:
            opex_carga = self.bess_ponta.calcular_opex_fp_energia(
                self.load.demanda_kw, self.bess_ponta.potencia_max_carga_kw,
                self.grid
            )
            saving_p = self.bess_ponta.calcular_saving_ponta(
                self.load.demanda_kw, self.grid
            )
            cf_bp = calc.cf_bess_ponta(
                capex           = self.bess_ponta.capex_r,
                custo_reposicao = self.bess_ponta.custo_reposicao_r,
                ano_reposicao   = self.bess_ponta.tempo_reposicao_anos,
                opex_fp_carga   = opex_carga,
                saving_ponta    = saving_p,
            )
            cfs.append(cf_bp)
            capex_total += self.bess_ponta.capex_r
            self._resultados["cf_bess_ponta"] = cf_bp

        # --- Gerador Ponta ---
        cf_gp = None
        if self.gen_ponta and self.lic.gen_ponta:
            cf_gp = calc.cf_gen_ponta(
                capex       = self.gen_ponta.capex_r,
                om          = self.gen_ponta.om_anual_r,
                vida_util   = self.gen_ponta.vida_util_anos,
                saving_ponta= opex_g["p_energia"],
            )
            cfs.append(cf_gp)
            capex_total += self.gen_ponta.capex_r
            self._resultados["cf_gen_ponta"] = cf_gp

        # --- New Grid ---
        if self.new_grid and self.lic.new_grid:
            cf_ng = {"CAPITAL": [-self.new_grid.capex_r] + [0.0] * self.params_cf.anos_projeto,
                     "REPLACEMENT": [0.0] * (self.params_cf.anos_projeto + 1),
                     "O&M": [0.0] * (self.params_cf.anos_projeto + 1),
                     "OPERATING_FP_ENERGIA": cf_g["OPERATING_FP_ENERGIA"],
                     "OPERATING_P_ENERGIA":  cf_g["OPERATING_P_ENERGIA"],
                     "OPERATING_FP_DEMANDA": cf_g["OPERATING_FP_DEMANDA"]}
            cfs.append(cf_ng)
            capex_total += self.new_grid.capex_r
            self._resultados["cf_new_grid"] = cf_ng

        # --- Totalização ---
        baseline  = calc.totalizar_cf([cf_g])
        proposta  = calc.totalizar_cf(cfs) if cfs else [0.0] * (self.params_cf.anos_projeto + 1)

        saving_serie = [p - b for p, b in zip(proposta, baseline)]
        fc_total     = [s + b for s, b in zip(saving_serie, baseline)]

        vpl      = calc.calcular_vpl(fc_total)
        tir      = calc.calcular_tir(fc_total)
        payback  = calc.calcular_payback(fc_total)
        roi      = calc.calcular_roi(vpl, capex_total)

        resultados = {
            "baseline_nominal":  baseline,
            "proposta_nominal":  proposta,
            "saving_serie":      saving_serie,
            "fc_total_nominal":  fc_total,
            "fc_total_descontado": calc.descontar_serie(fc_total),
            "vpl":               round(vpl, 2),
            "tir":               round(tir * 100, 4) if tir else None,
            "payback_anos":      payback,
            "roi":               round(roi, 4),
            "capex_total":       capex_total,
            "viavel":            (tir is not None and tir > self.params_cf.taxa_desconto
                                  if tir else False),
            "indicadores": {
                "taxa_desconto":     self.params_cf.taxa_desconto,
                "inflacao":          self.params_cf.inflacao,
                "anos_projeto":      self.params_cf.anos_projeto,
                "taxa_desconto_real":self.params_cf.taxa_desconto_real,
            },
        }
        self._resultados["cf_consolidado"] = resultados
        return resultados

    # ── Sumário executivo ─────────────────────────────────────────────
    def gerar_summary(self) -> dict:
        self.lic.requer("summary")
        cf = self._resultados.get("cf_consolidado", {})
        opex_g = self.calcular_opex_grid()["anual"] if self.grid and self.load else {}

        return {
            "projeto": {
                "concessionaria":   self.grid.concessionaria if self.grid else None,
                "subgrupo":         self.grid.subgrupo if self.grid else None,
                "demanda_maxima_kw":self.load.demanda_maxima_kw if self.load else None,
                "potencia_solar_kwp":self.solar.potencia_cc_kwp if self.solar else None,
                "energia_bess_kwh": self.bess_ponta.energia_dod80_kwh if self.bess_ponta else None,
            },
            "custos": {
                "opex_grid_anual":  opex_g.get("total"),
                "capex_total":      cf.get("capex_total"),
            },
            "indicadores": {
                "vpl":     cf.get("vpl"),
                "tir_pct": cf.get("tir"),
                "payback": cf.get("payback_anos"),
                "roi":     cf.get("roi"),
                "viavel":  cf.get("viavel"),
            },
            "modulos_ativos": {
                "load":       self.lic.load,
                "grid":       self.lic.grid,
                "solar":      self.lic.solar,
                "bess_ponta": self.lic.bess_ponta,
                "gen_ponta":  self.lic.gen_ponta,
                "gen_form":   self.lic.gen_form,
                "bess_form":  self.lic.bess_form,
                "new_grid":   self.lic.new_grid,
                "cf":         self.lic.cf,
                "summary":    self.lic.summary,
            },
        }

    def para_json(self) -> str:
        """Serializa todos os resultados para JSON."""
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
# DADOS DE EXEMPLO (da planilha original)
# ═══════════════════════════════════════════════════════════════════════

def exemplo_planilha_original() -> EstudoViabilidade:
    """
    Instancia o motor com os dados exatos extraídos da planilha
    ESTUDO_DE_VIABILIDADE_Híbrido_27-06-2024.
    """
    lic = LicencaModulos(
        load=True, grid=True, solar=True, bess_ponta=True,
        gen_ponta=False, gen_form=False, bess_form=False,
        new_grid=False, cf=True, summary=True,
    )
    estudo = EstudoViabilidade(lic)

    # ── Input Load ────────────────────────────────────────────────────
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
    energia_ponta = [2662.80,5453.28,6108.06,4160.52,4073.58,2931.60,
                     1882.23,4177.74,5302.71,5503.05,5112.45,3932.04]
    energia_fp    = [12627.09,22532.58,25641.63,15337.77,14943.18,11676.42,
                     9338.28,16476.39,21940.80,22099.56,23826.81,18554.55]
    load = InputLoad(
        demanda_maxima_kw=238.56,
        demanda_kw=demanda_kw,
        energia_ponta_kwh=energia_ponta,
        energia_fp_kwh=energia_fp,
    )
    estudo.carregar_load(load)

    # ── Input Grid (Cemig-D A4 Verde 2023) ────────────────────────────
    grid = InputGrid(
        concessionaria="Cemig-D", ano_revisao=2023,
        subgrupo="A4", modalidade="Verde",
        tusd_ponta=1.326, tusd_fp=0.118,
        te_ponta=0.379, te_fp=0.232,
        tusd_fio_a_p=0.25728, tusd_fio_b_p=1.130074,
        tusd_tfsee_p=0.000341, tusd_pd_p=0.0093775,
        te_pd_p=0.002728, outros_p=0.305195,
        tusd_fio_a_fp=0.0, tusd_fio_b_fp=0.0,
        tusd_tfsee_fp=0.00042, tusd_pd_fp=0.00042,
        te_pd_fp=0.0028, outros_fp=0.34640,
        demanda_sem_posto=16.54,
        tusd_fio_a_dem=5.544208, tusd_fio_b_dem=13.513180,
        outros_dem=-2.520696, demanda_geracao=9.45,
        fator_k=4.8714, demanda_contratada_kw=250.488,
    )
    estudo.carregar_grid(grid)

    # ── Input Solar SCDEE (300 kWp / GDIII / SP) ─────────────────────
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
    solar = InputSolarSCDEE(
        estado="São Paulo", potencia_ca_kw=211.27, potencia_cc_kwp=300.0,
        sobrecarga_inversor=1.42, capex_r=885000, om_anual_r=1500,
        degradacao_ano1=0.02, degradacao_demais=0.0055,
        custo_troca_inversor_r=50000, ano_troca_inversor=12,
        modalidade_gd="GDIII", data_estudo_ano=2024,
        tusd_ponta=1.326, tusd_fp=0.118, te_ponta=0.379, te_fp=0.232,
        tusd_fio_a_p=0.25728, tusd_fio_b_p=1.130074,
        outros_p=0.305195, demanda_geracao_r=9.45,
        potencia_gerada_kw=potencia_gerada,
        potencia_injetada_kw=[[-v for v in linha] for linha in potencia_gerada],
        fonte_dados="manual",
    )
    estudo.carregar_solar_scdee(solar)

    # ── Input BESS Ponta ──────────────────────────────────────────────
    bess = InputBESSPonta(
        capex_r=5_526_000, custo_reposicao_r=5_526_000,
        tempo_reposicao_anos=14, vida_util_anos=14,
        percentual_eol=0.60, n_ciclos_dod80=4882.5,
        n_ciclos_dod100=3906, dod_operacional=0.80,
        n_bms_por_br=18, n_bms_total=180, n_brs=10,
        brs_serie=1, brs_paralelo=10,
        tensao_nominal_v=691.2, capacidade_c10_ah=2890,
        corrente_max_carga_a=330, corrente_max_descarga_a=330,
        potencia_max_carga_kw=228.096, potencia_max_descarga_kw=228.096,
        eta_pcs=0.982, eta_bateria=0.9885, eta_sys=0.99,
        eta_total=0.961, energia_dod80_kwh=1598.05,
        energia_dod100_kwh=1997.57, energia_dod80_pos_pcs=1535.73,
        energia_dod100_pos_pcs=1919.66, tempo_carga_h=7.006,
        tempo_descarga_h=7.006,
    )
    estudo.carregar_bess_ponta(bess)

    # ── Parâmetros CF (da aba Comparação Econômica) ───────────────────
    estudo.configurar_cf(ParamsCF(
        taxa_desconto=0.08,
        inflacao=0.0393,
        anos_projeto=25,
        reajuste_tarifa_ponta=0.01,
        reajuste_tarifa_fp=0.00,
        reajuste_demanda_spt=0.008,
    ))

    return estudo


# ═══════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(
        description="Motor de Estudo de Viabilidade — Sistema Híbrido"
    )
    parser.add_argument("--exemplo", action="store_true",
                        help="Executar com dados da planilha original")
    parser.add_argument("--json",    action="store_true",
                        help="Exportar resultados em JSON")
    args = parser.parse_args()

    if args.exemplo or True:
        print("=" * 70)
        print("  MOTOR DE VIABILIDADE — SISTEMA HÍBRIDO")
        print("  Dados: ESTUDO_DE_VIABILIDADE_Híbrido_27-06-2024")
        print("=" * 70)

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
            print("\n--- JSON ---")
            print(estudo.para_json())
