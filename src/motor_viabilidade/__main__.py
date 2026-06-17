"""
Entrypoint de linha de comando do pacote.

Execução:
  python -m motor_viabilidade --exemplo     # estudo híbrido da planilha
  python -m motor_viabilidade --gridzero    # análise GridZero (Canal Solar N°33)
  python -m motor_viabilidade --ambos       # ambos
"""
from __future__ import annotations

import argparse
import sys

from .InputGridZero import AnaliseComparativaGridZero, InputGridZero
from .exemplos import exemplo_gridzero_planilha, exemplo_planilha_original


def main() -> None:
    # Garante saída UTF-8 mesmo em consoles legados (ex.: cp1252 no Windows),
    # já que a saída usa caracteres de moldura (═ ─) e acentuação.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

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


if __name__ == "__main__":
    main()
