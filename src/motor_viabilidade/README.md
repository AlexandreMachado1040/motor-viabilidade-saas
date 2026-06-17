# motor_viabilidade — pacote modular

Modularização do motor de Estudo de Viabilidade (Sistema Híbrido + GridZero),
extraído de `.docs/motor_viabilidade - Versão com Grid-zero.py`.

Cada módulo do estudo (a partir de **INPUT-LOAD**; as abas CAPA e README foram
desconsideradas) vive em seu próprio subpacote — **uma pasta por módulo**.

## Estrutura

```
src/motor_viabilidade/
├── __init__.py                  ← API pública (re-exporta todas as classes)
├── __main__.py                  ← CLI (python -m motor_viabilidade)
├── exemplos.py                  ← datasets de referência (planilha + GridZero)
├── common.py                    ← MESES, HORAS, log (compartilhados)
├── LicencaModulos/              ← controle de acesso por módulo (SaaS)
├── ConfigAPIANEEL/              ← autenticação OAuth2 Dynamics 365
├── ClienteAPIANEEL/             ← busca tarifas via OData + cache local
├── InputLoad/                   ← MOD 1: memória de massa demanda/energia
├── InputGrid/                   ← MOD 2: tarifas distribuidora + API ANEEL
├── InputSolarSCDEE/             ← MOD 3: GD GDII/GDIII + solarimetria integrada
├── InputBESSPonta/              ← MOD 4: bateria redução ponta
├── InputGeradorPonta/           ← MOD 5: gerador diesel ponta
├── InputGeradorFormador/        ← MOD 6: gerador grid-forming
├── InputBESSFormador/           ← MOD 7: BESS grid-forming
├── SolarHibridoParams/          ← Solar para sistemas híbridos
├── InputNewGrid/                ← MOD 8: nova rede elétrica
├── InputGridZero/               ← MOD GZ: sistema sem injeção na rede (GridZero)
├── ParamsCF/                    ← parâmetros econômicos (TMA, inflação, anos)
├── CalculadoraOPEXGrid/         ← OPEX baseline mensal/anual
├── CalculadoraCF/               ← FC nominal + descontado, VPL, TIR, Payback
├── IntegradorSolarimetrico/     ← integra SONDA/PVGIS/TMY → matriz 12×24
└── EstudoViabilidade/           ← orquestrador principal (módulo a módulo)
```

Cada subpacote tem um `__init__.py` que re-exporta sua classe e um arquivo de
implementação (ex.: `InputLoad/input_load.py`).

## Dependências

```
pip install numpy pandas requests msal python-dateutil
```

`requests` e `msal` só são exigidos em tempo de execução pelo `ClienteAPIANEEL`
(import preguiçoso). O motor híbrido e o GridZero rodam sem eles.

## Uso

```python
from motor_viabilidade import EstudoViabilidade, LicencaModulos, InputGrid, InputGridZero

lic    = LicencaModulos(load=True, grid=True, gridzero=True, cf=True)
estudo = EstudoViabilidade(lic)
estudo.carregar_grid(InputGrid())
resultado = estudo.calcular_gridzero(InputGridZero())
```

CLI:

```
python -m motor_viabilidade --exemplo     # estudo híbrido da planilha
python -m motor_viabilidade --gridzero    # análise GridZero (Canal Solar N°33)
python -m motor_viabilidade --ambos       # ambos
python -m motor_viabilidade --gridzero --csv --json
```

## Módulos solarimétricos (pendentes)

O `IntegradorSolarimetrico` faz import preguiçoso de três coletores ainda **não
incluídos** neste pacote (ficam no diretório de execução ou no PYTHONPATH):

- `sonda_collector.py` — Rede SONDA/INPE (21 estações)
- `pvgis_collector.py` — PVGIS 5.2 API REST (JRC/CE)
- `tmy_generator.py`   — TMY ISO 15927-4 (Finkelstein-Schafer)

Quando ausentes, a matriz solar é retornada zerada (com aviso no log).
