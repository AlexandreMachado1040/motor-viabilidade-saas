"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MOTOR DE ESTUDO DE VIABILIDADE — SISTEMA HÍBRIDO (pacote modular)          ║
║  Baseado em: ESTUDO_DE_VIABILIDADE_Híbrido_27-06-2024                       ║
║  Módulos licenciáveis por assinatura (SaaS modular)                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Cada módulo do estudo vive em seu próprio subpacote (uma pasta por módulo):

  LicencaModulos          → controle de acesso por módulo (SaaS)
  ConfigAPIANEEL          → autenticação OAuth2 Dynamics 365
  ClienteAPIANEEL         → busca tarifas via OData + cache local
  InputLoad               → MOD 1: memória de massa demanda/energia
  InputGrid               → MOD 2: tarifas distribuidora + API ANEEL
  InputSolarSCDEE         → MOD 3: GD GDII/GDIII + solarimetria integrada
  InputBESSPonta          → MOD 4: bateria redução ponta
  InputGeradorPonta       → MOD 5: gerador diesel ponta
  InputGeradorFormador    → MOD 6: gerador grid-forming
  InputBESSFormador       → MOD 7: BESS grid-forming
  SolarHibridoParams      → Solar para sistemas híbridos
  InputNewGrid            → MOD 8: nova rede elétrica
  InputGridZero           → MOD GZ: sistema sem injeção na rede (GridZero)
  ParamsCF                → parâmetros econômicos (TMA, inflação, anos)
  CalculadoraOPEXGrid     → OPEX baseline mensal/anual
  CalculadoraCF           → FC nominal + descontado, VPL, TIR, Payback
  IntegradorSolarimetrico → integra SONDA/PVGIS/TMY → matriz 12×24
  EstudoViabilidade       → orquestrador principal (módulo a módulo)

Dependências:
  pip install numpy pandas requests msal python-dateutil

Uso básico:
  from motor_viabilidade import EstudoViabilidade, LicencaModulos, InputGridZero
  lic    = LicencaModulos(load=True, grid=True, gridzero=True, cf=True)
  estudo = EstudoViabilidade(lic)
  estudo.carregar_grid(InputGrid())
  resultado = estudo.calcular_gridzero(InputGridZero())
"""
from __future__ import annotations

from .common import MESES, HORAS, log
from .LicencaModulos import LicencaModulos
from .ConfigAPIANEEL import ConfigAPIANEEL
from .ClienteAPIANEEL import ClienteAPIANEEL
from .InputLoad import InputLoad
from .InputGrid import InputGrid
from .SimuladorTarifas import InputSimuladorTarifas, SimuladorTarifas
from .InputSolarSCDEE import InputSolarSCDEE
from .InputBESSPonta import InputBESSPonta
from .InputGeradorPonta import InputGeradorPonta
from .InputGeradorFormador import InputGeradorFormador
from .InputBESSFormador import InputBESSFormador
from .SolarHibridoParams import SolarHibridoParams
from .InputNewGrid import InputNewGrid
from .InputGridZero import (
    AnaliseComparativaGridZero,
    CalculadoraGridZero,
    InputGridZero,
    ResultadoGridZero,
)
from .ParamsCF import ParamsCF
from .CalculadoraOPEXGrid import CalculadoraOPEXGrid
from .CalculadoraCF import CalculadoraCF
from .IntegradorSolarimetrico import IntegradorSolarimetrico
from .EstudoViabilidade import EstudoViabilidade

__all__ = [
    "MESES", "HORAS", "log",
    "LicencaModulos",
    "ConfigAPIANEEL", "ClienteAPIANEEL",
    "InputLoad", "InputGrid", "InputSolarSCDEE",
    "InputSimuladorTarifas", "SimuladorTarifas",
    "InputBESSPonta", "InputGeradorPonta", "InputGeradorFormador",
    "InputBESSFormador", "SolarHibridoParams", "InputNewGrid",
    "InputGridZero", "ResultadoGridZero", "CalculadoraGridZero",
    "AnaliseComparativaGridZero",
    "ParamsCF", "CalculadoraOPEXGrid", "CalculadoraCF",
    "IntegradorSolarimetrico", "EstudoViabilidade",
]
