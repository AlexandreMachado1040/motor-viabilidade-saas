"""Schemas do simulador de modalidades tarifárias (MOD 2).

Espelham motor_viabilidade.SimuladorTarifas: 12 meses de demanda medida e
consumo por posto, demandas contratadas e as tarifas digitadas de cada
modalidade. Modalidade sem tarifa (null) fica fora da comparação."""
from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field

# Teto de 12 no schema só barra payload gigante; faltar mês cai na validação
# do motor, que devolve a mensagem legível em `erros`.
Meses = Annotated[list[float], Field(max_length=12)]


class TarifasConvencionalPayload(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    demanda: float = Field(ge=0)
    consumo: float = Field(ge=0)


class TarifasAzulPayload(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    demanda_ponta: float = Field(ge=0)
    demanda_fp: float = Field(ge=0)
    consumo_ponta: float = Field(ge=0)
    consumo_fp: float = Field(ge=0)
    consumo_ponta_umido: Optional[float] = Field(default=None, ge=0)
    consumo_fp_umido: Optional[float] = Field(default=None, ge=0)


class TarifasVerdePayload(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    demanda: float = Field(ge=0)
    consumo_ponta: float = Field(ge=0)
    consumo_fp: float = Field(ge=0)
    consumo_ponta_umido: Optional[float] = Field(default=None, ge=0)
    consumo_fp_umido: Optional[float] = Field(default=None, ge=0)


class TarifasBaixaTensaoPayload(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    consumo: float = Field(ge=0)


class SimuladorTarifasPayload(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    demanda_ponta_kw: Meses
    demanda_fp_kw: Meses
    consumo_ponta_kwh: Meses
    consumo_fp_kwh: Meses
    demanda_contratada_kw: float = 60.0
    demanda_contratada_ponta_kw: float = 60.0
    demanda_contratada_fp_kw: float = 60.0
    tolerancia_ultrapassagem: float = 0.05
    fator_ultrapassagem: float = 2.0
    convencional: Optional[TarifasConvencionalPayload] = None
    azul: Optional[TarifasAzulPayload] = None
    verde: Optional[TarifasVerdePayload] = None
    baixa_tensao: Optional[TarifasBaixaTensaoPayload] = None


class ModalidadeResultado(BaseModel):
    modalidade: str
    custo_anual: float
    custo_mensal: list[float]
    componentes: dict[str, float]
    ultrapassagem_anual: float
    meses_com_ultrapassagem: int


class DemandaSugeridaResultado(BaseModel):
    modalidade: str
    demanda_kw: Optional[float] = None
    demanda_ponta_kw: Optional[float] = None
    demanda_fp_kw: Optional[float] = None
    custo_anual: float
    economia_anual: float


class SimuladorTarifasResumo(BaseModel):
    valido: bool = True
    erros: list[str] = Field(default_factory=list)
    modalidades: list[ModalidadeResultado] = Field(default_factory=list)
    recomendada: Optional[str] = None
    economia_vs_atual: dict[str, float] = Field(default_factory=dict)
    demandas_sugeridas: list[DemandaSugeridaResultado] = Field(default_factory=list)
