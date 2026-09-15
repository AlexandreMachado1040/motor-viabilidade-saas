"""
MOD 2 — Simulador de modalidades tarifárias (Convencional, Azul, Verde, BT).

Porta da planilha ``.docs/SIMULADOR TARIFAS ANUAL_V1.xls`` (aba "Simulação
anual"): para 12 meses de demanda medida e consumo por posto, calcula o custo
anual de cada modalidade e aponta a mais barata.

Regras (REN ANEEL 1.000/2021):
  - demanda faturável = max(medida, contratada);
  - ultrapassagem quando medida > contratada × (1 + tolerância), cobrada sobre
    (medida − contratada) × tarifa de demanda × fator (2 por padrão);
  - Convencional e Verde têm demanda única (maior entre ponta e fora ponta);
    Azul contrata e fatura ponta e fora ponta separadamente;
  - Baixa Tensão só fatura consumo, a uma tarifa única.

Diferenças em relação à planilha:
  - o limite de ultrapassagem sai da demanda contratada informada (a planilha
    tem 63 kW fixo na fórmula, que só vale para 60 kW contratados);
  - a demanda contratada sugerida é a que minimiza o custo anual, buscada nos
    pontos de quebra da função de custo, e não a heurística max(medida)/1,05.

As tarifas são as digitadas pelo usuário (R$/kW e R$/kWh, já com impostos se
for o caso) — o simulador não aplica PIS/COFINS/ICMS por conta própria.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Período seco: maio a novembro (meses 5..11); úmido: dezembro a abril.
MESES_SECOS = frozenset(range(5, 12))

# Folga numérica: contratada = medida/1,05 não pode virar ultrapassagem por
# arredondamento de ponto flutuante.
_EPS = 1e-9


@dataclass
class TarifasConvencional:
    demanda: float            # R$/kW
    consumo: float            # R$/kWh


@dataclass
class TarifasAzul:
    demanda_ponta: float
    demanda_fp: float
    consumo_ponta: float
    consumo_fp: float
    consumo_ponta_umido: Optional[float] = None   # None → igual ao seco
    consumo_fp_umido: Optional[float] = None


@dataclass
class TarifasVerde:
    demanda: float
    consumo_ponta: float
    consumo_fp: float
    consumo_ponta_umido: Optional[float] = None
    consumo_fp_umido: Optional[float] = None


@dataclass
class TarifasBaixaTensao:
    consumo: float


@dataclass
class InputSimuladorTarifas:
    demanda_ponta_kw: list[float] = field(default_factory=list)
    demanda_fp_kw: list[float] = field(default_factory=list)
    consumo_ponta_kwh: list[float] = field(default_factory=list)
    consumo_fp_kwh: list[float] = field(default_factory=list)

    demanda_contratada_kw: float = 60.0          # Convencional e Verde
    demanda_contratada_ponta_kw: float = 60.0    # Azul
    demanda_contratada_fp_kw: float = 60.0       # Azul

    tolerancia_ultrapassagem: float = 0.05
    fator_ultrapassagem: float = 2.0

    convencional: Optional[TarifasConvencional] = None
    azul: Optional[TarifasAzul] = None
    verde: Optional[TarifasVerde] = None
    baixa_tensao: Optional[TarifasBaixaTensao] = None

    def validar(self) -> list[str]:
        erros: list[str] = []
        for nome in ("demanda_ponta_kw", "demanda_fp_kw", "consumo_ponta_kwh", "consumo_fp_kwh"):
            valores = getattr(self, nome)
            if len(valores) != 12:
                erros.append(f"{nome} deve ter 12 meses (recebido: {len(valores)}).")
            elif any(v < 0 for v in valores):
                erros.append(f"{nome} não pode ter valor negativo.")
        for nome in ("demanda_contratada_kw", "demanda_contratada_ponta_kw", "demanda_contratada_fp_kw"):
            if getattr(self, nome) < 0:
                erros.append(f"{nome} não pode ser negativa.")
        if self.tolerancia_ultrapassagem < 0:
            erros.append("tolerancia_ultrapassagem não pode ser negativa.")
        if self.fator_ultrapassagem < 0:
            erros.append("fator_ultrapassagem não pode ser negativo.")
        if not any((self.convencional, self.azul, self.verde, self.baixa_tensao)):
            erros.append("Informe as tarifas de pelo menos uma modalidade.")
        return erros


@dataclass
class ResultadoModalidade:
    modalidade: str
    custo_anual: float
    custo_mensal: list[float]
    # Custo anual por componente da fatura (ex.: "Demanda ponta", "Consumo fora ponta").
    componentes: dict[str, float]
    ultrapassagem_anual: float
    meses_com_ultrapassagem: int
    componentes_mensais: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class DemandaSugerida:
    modalidade: str
    demanda_kw: Optional[float] = None           # Convencional/Verde
    demanda_ponta_kw: Optional[float] = None     # Azul
    demanda_fp_kw: Optional[float] = None        # Azul
    custo_anual: float = 0.0
    economia_anual: float = 0.0                  # vs. a contratada atual


@dataclass
class ResultadoSimulacao:
    modalidades: list[ResultadoModalidade]
    recomendada: Optional[str]
    economia_vs_atual: dict[str, float]          # modalidade → custo − custo da recomendada
    demandas_sugeridas: list[DemandaSugerida]


def _tarifa_mes(mes: int, seco: float, umido: Optional[float]) -> float:
    return seco if mes in MESES_SECOS or umido is None else umido


class SimuladorTarifas:
    def __init__(self, entrada: InputSimuladorTarifas):
        self.e = entrada

    # ── Demanda ────────────────────────────────────────────────────────────
    def _demanda(self, medidas: list[float], contratada: float, tarifa: float) -> tuple[list[float], list[float]]:
        """Custo mensal de demanda faturável e de ultrapassagem."""
        limite = contratada * (1 + self.e.tolerancia_ultrapassagem)
        fat, ultra = [], []
        for m in medidas:
            fat.append(max(m, contratada) * tarifa)
            excede = m > limite + _EPS
            ultra.append((m - contratada) * tarifa * self.e.fator_ultrapassagem if excede else 0.0)
        return fat, ultra

    def _custo_demanda_anual(self, medidas: list[float], contratada: float, tarifa: float) -> float:
        fat, ultra = self._demanda(medidas, contratada, tarifa)
        return sum(fat) + sum(ultra)

    def _demanda_otima(self, medidas: list[float], tarifa: float, atual: float) -> tuple[float, float]:
        """Contratada que minimiza demanda + ultrapassagem no ano.

        O custo é linear por partes na contratada, com quebras em cada medida
        (troca de max) e em cada medida/(1+tol) (liga/desliga ultrapassagem);
        o mínimo está num desses pontos. Empate → mantém a contratada atual
        (ex.: tarifa zero não sugere trocar para 0 kW); senão, a menor.
        """
        tol = self.e.tolerancia_ultrapassagem
        candidatos = {0.0, atual}
        for m in medidas:
            candidatos.add(m)
            candidatos.add(m / (1 + tol))
        melhor = min(sorted(candidatos), key=lambda c: (
            round(self._custo_demanda_anual(medidas, c, tarifa), 6), c != atual, c))
        return melhor, self._custo_demanda_anual(medidas, melhor, tarifa)

    @property
    def _demanda_unica(self) -> list[float]:
        return [max(p, f) for p, f in zip(self.e.demanda_ponta_kw, self.e.demanda_fp_kw)]

    # ── Modalidades ────────────────────────────────────────────────────────
    def _resultado(self, nome: str, linhas: dict[str, list[float]], ultra: list[float]) -> ResultadoModalidade:
        mensal = [sum(v[i] for v in linhas.values()) for i in range(12)]
        return ResultadoModalidade(
            modalidade=nome,
            custo_anual=sum(mensal),
            custo_mensal=mensal,
            componentes={k: sum(v) for k, v in linhas.items()},
            ultrapassagem_anual=sum(ultra),
            meses_com_ultrapassagem=sum(1 for u in ultra if u > 0),
            componentes_mensais={k: list(v) for k, v in linhas.items()},
        )

    def convencional(self) -> Optional[ResultadoModalidade]:
        t = self.e.convencional
        if t is None:
            return None
        fat, ultra = self._demanda(self._demanda_unica, self.e.demanda_contratada_kw, t.demanda)
        consumo = [(p + f) * t.consumo for p, f in zip(self.e.consumo_ponta_kwh, self.e.consumo_fp_kwh)]
        return self._resultado("Convencional", {
            "Demanda": fat, "Ultrapassagem": ultra, "Consumo": consumo,
        }, ultra)

    def azul(self) -> Optional[ResultadoModalidade]:
        t = self.e.azul
        if t is None:
            return None
        fat_p, ultra_p = self._demanda(self.e.demanda_ponta_kw, self.e.demanda_contratada_ponta_kw, t.demanda_ponta)
        fat_f, ultra_f = self._demanda(self.e.demanda_fp_kw, self.e.demanda_contratada_fp_kw, t.demanda_fp)
        c_p = [q * _tarifa_mes(i + 1, t.consumo_ponta, t.consumo_ponta_umido) for i, q in enumerate(self.e.consumo_ponta_kwh)]
        c_f = [q * _tarifa_mes(i + 1, t.consumo_fp, t.consumo_fp_umido) for i, q in enumerate(self.e.consumo_fp_kwh)]
        ultra = [a + b for a, b in zip(ultra_p, ultra_f)]
        return self._resultado("Azul", {
            "Demanda ponta": fat_p, "Demanda fora ponta": fat_f,
            "Ultrapassagem ponta": ultra_p, "Ultrapassagem fora ponta": ultra_f,
            "Consumo ponta": c_p, "Consumo fora ponta": c_f,
        }, ultra)

    def verde(self) -> Optional[ResultadoModalidade]:
        t = self.e.verde
        if t is None:
            return None
        fat, ultra = self._demanda(self._demanda_unica, self.e.demanda_contratada_kw, t.demanda)
        c_p = [q * _tarifa_mes(i + 1, t.consumo_ponta, t.consumo_ponta_umido) for i, q in enumerate(self.e.consumo_ponta_kwh)]
        c_f = [q * _tarifa_mes(i + 1, t.consumo_fp, t.consumo_fp_umido) for i, q in enumerate(self.e.consumo_fp_kwh)]
        return self._resultado("Verde", {
            "Demanda": fat, "Ultrapassagem": ultra,
            "Consumo ponta": c_p, "Consumo fora ponta": c_f,
        }, ultra)

    def baixa_tensao(self) -> Optional[ResultadoModalidade]:
        t = self.e.baixa_tensao
        if t is None:
            return None
        consumo = [(p + f) * t.consumo for p, f in zip(self.e.consumo_ponta_kwh, self.e.consumo_fp_kwh)]
        return self._resultado("Baixa Tensão", {"Consumo": consumo}, [0.0] * 12)

    # ── Demanda sugerida ───────────────────────────────────────────────────
    def demandas_sugeridas(self, resultados: dict[str, ResultadoModalidade]) -> list[DemandaSugerida]:
        sugestoes: list[DemandaSugerida] = []
        unica = self._demanda_unica
        for nome, tarifas in (("Convencional", self.e.convencional), ("Verde", self.e.verde)):
            if tarifas is None:
                continue
            atual = self._custo_demanda_anual(unica, self.e.demanda_contratada_kw, tarifas.demanda)
            kw, custo_dem = self._demanda_otima(unica, tarifas.demanda, self.e.demanda_contratada_kw)
            base = resultados[nome].custo_anual
            sugestoes.append(DemandaSugerida(
                modalidade=nome, demanda_kw=kw,
                custo_anual=base - atual + custo_dem, economia_anual=atual - custo_dem,
            ))
        t = self.e.azul
        if t is not None:
            atual = (self._custo_demanda_anual(self.e.demanda_ponta_kw, self.e.demanda_contratada_ponta_kw, t.demanda_ponta)
                     + self._custo_demanda_anual(self.e.demanda_fp_kw, self.e.demanda_contratada_fp_kw, t.demanda_fp))
            kw_p, custo_p = self._demanda_otima(self.e.demanda_ponta_kw, t.demanda_ponta, self.e.demanda_contratada_ponta_kw)
            kw_f, custo_f = self._demanda_otima(self.e.demanda_fp_kw, t.demanda_fp, self.e.demanda_contratada_fp_kw)
            base = resultados["Azul"].custo_anual
            sugestoes.append(DemandaSugerida(
                modalidade="Azul", demanda_ponta_kw=kw_p, demanda_fp_kw=kw_f,
                custo_anual=base - atual + custo_p + custo_f, economia_anual=atual - custo_p - custo_f,
            ))
        return sugestoes

    def simular(self) -> ResultadoSimulacao:
        erros = self.e.validar()
        if erros:
            raise ValueError("; ".join(erros))
        calculadas = [r for r in (self.convencional(), self.azul(), self.verde(), self.baixa_tensao()) if r is not None]
        por_nome = {r.modalidade: r for r in calculadas}
        recomendada = min(calculadas, key=lambda r: r.custo_anual)
        return ResultadoSimulacao(
            modalidades=calculadas,
            recomendada=recomendada.modalidade,
            economia_vs_atual={r.modalidade: r.custo_anual - recomendada.custo_anual for r in calculadas},
            demandas_sugeridas=self.demandas_sugeridas(por_nome),
        )


# Identificador da modalidade na API → nome exibido no resultado.
MODALIDADES = {
    "convencional": "Convencional",
    "azul": "Azul",
    "verde": "Verde",
    "baixa_tensao": "Baixa Tensão",
}


def simular_modalidade(entrada: InputSimuladorTarifas, modalidade: str) -> ResultadoModalidade:
    """Fatura de uma modalidade só (a escolhida para o estudo)."""
    if modalidade not in MODALIDADES:
        raise ValueError(f"Modalidade desconhecida: {modalidade!r}.")
    erros = entrada.validar()
    if erros:
        raise ValueError("; ".join(erros))
    resultado = getattr(SimuladorTarifas(entrada), modalidade)()
    if resultado is None:
        raise ValueError(f"Informe as tarifas da modalidade {MODALIDADES[modalidade]}.")
    return resultado


def opex_grid_da_fatura(r: ResultadoModalidade, e: InputSimuladorTarifas) -> dict:
    """Fatura da modalidade no formato de EstudoViabilidade.calcular_opex_grid().

    Como a tarifa digitada é final (TUSD + TE juntas), o consumo vai inteiro
    para as chaves ``tusd_*`` e ``te_*`` fica zerado. Nas modalidades de
    tarifa única (Convencional, BT) o custo de consumo é repartido entre
    ponta e fora ponta pela energia de cada posto. Demanda e ultrapassagem
    somam em ``demanda_spt``.
    """
    cm = r.componentes_mensais
    zero = [0.0] * 12
    if "Consumo" in cm:
        c_ponta, c_fp = [], []
        for custo, p, f in zip(cm["Consumo"], e.consumo_ponta_kwh, e.consumo_fp_kwh):
            parte = p / (p + f) if p + f > 0 else 0.0
            c_ponta.append(custo * parte)
            c_fp.append(custo - custo * parte)
    else:
        c_ponta, c_fp = cm.get("Consumo ponta", zero), cm.get("Consumo fora ponta", zero)
    demanda = [sum(v[i] for k, v in cm.items() if not k.startswith("Consumo")) for i in range(12)]
    total = [a + b + c for a, b, c in zip(c_ponta, c_fp, demanda)]
    return {
        "mensal": {
            "tusd_ponta": c_ponta, "tusd_fp": c_fp, "te_ponta": zero, "te_fp": zero,
            "demanda_spt": demanda, "total": total,
        },
        "anual": {
            "fp_energia": sum(c_fp), "p_energia": sum(c_ponta),
            "fp_demanda": sum(demanda), "total": sum(total),
        },
    }


def tarifas_medias_consumo(r: ResultadoModalidade, e: InputSimuladorTarifas) -> tuple[float, float]:
    """Tarifa média de consumo (R$/kWh) de ponta e fora ponta no ano.

    Média ponderada pela energia, o que já absorve a tarifa úmida. Sem
    energia no posto, vale a tarifa do período seco digitada.
    """
    anual = opex_grid_da_fatura(r, e)["anual"]
    kwh_p, kwh_f = sum(e.consumo_ponta_kwh), sum(e.consumo_fp_kwh)
    nome = next(k for k, v in MODALIDADES.items() if v == r.modalidade)
    t = getattr(e, nome)
    seco_p = getattr(t, "consumo_ponta", None) or getattr(t, "consumo", 0.0)
    seco_f = getattr(t, "consumo_fp", None) or getattr(t, "consumo", 0.0)
    return (
        anual["p_energia"] / kwh_p if kwh_p > 0 else seco_p,
        anual["fp_energia"] / kwh_f if kwh_f > 0 else seco_f,
    )


def exemplo_simulador_tarifas() -> InputSimuladorTarifas:
    """Dados da aba "Simulação anual" da planilha SIMULADOR TARIFAS ANUAL_V1.

    A planilha deixa meses em branco (consumo de ponta em mai/jun/out/dez,
    fora ponta em jun/dez, demandas em dez). Aqui eles foram completados com a
    média dos meses informados (demanda de dezembro = novembro), só para o
    exemplo ter 12 meses coerentes.
    """
    return InputSimuladorTarifas(
        demanda_ponta_kw=[60.0, 60.0, 60.0, 60.02, 60.0, 60.0, 60.0, 69.18, 66.22, 60.0, 68.68, 68.68],
        demanda_fp_kw=[60.0, 69.77, 74.1, 90.23, 60.0, 60.0, 62.19, 60.0, 61.7, 60.0, 67.99, 67.99],
        consumo_ponta_kwh=[1542.22, 1844.65, 1814.61, 2394.12, 2090.58, 2090.58, 2130.24, 2353.67,
                           2360.56, 2090.58, 2284.6, 2090.58],
        consumo_fp_kwh=[15916.2, 17655.42, 16580.4, 17689.86, 16082.09, 16865.85, 16471.41, 15362.7,
                        16265.52, 17701.69, 18933.26, 16865.85],
        demanda_contratada_kw=60.0,
        demanda_contratada_ponta_kw=60.0,
        demanda_contratada_fp_kw=60.0,
        convencional=TarifasConvencional(demanda=30.53, consumo=0.3242),
        azul=TarifasAzul(demanda_ponta=28.41, demanda_fp=10.07, consumo_ponta=0.44734, consumo_fp=0.31),
        verde=TarifasVerde(demanda=15.54448, consumo_ponta=1.75344, consumo_fp=0.48316),
        baixa_tensao=None,
    )


__all__ = [
    "MESES_SECOS",
    "TarifasConvencional", "TarifasAzul", "TarifasVerde", "TarifasBaixaTensao",
    "InputSimuladorTarifas", "ResultadoModalidade", "DemandaSugerida", "ResultadoSimulacao",
    "SimuladorTarifas", "exemplo_simulador_tarifas",
    "MODALIDADES", "simular_modalidade", "opex_grid_da_fatura", "tarifas_medias_consumo",
]
