"""Cliente de busca de tarifas da ANEEL via OData v4 + cache local JSON."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..common import log

if TYPE_CHECKING:
    from ..ConfigAPIANEEL import ConfigAPIANEEL


class ClienteAPIANEEL:
    """
    Cliente para buscar tarifas diretamente do BI da ANEEL
    (Microsoft Dynamics 365 / Dataverse OData v4).
    Fluxo: MSAL client_credentials → Bearer token → OData query → cache JSON.
    """

    def __init__(self, config: "ConfigAPIANEEL"):
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


__all__ = ["ClienteAPIANEEL"]
