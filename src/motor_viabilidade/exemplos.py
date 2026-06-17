"""
Dados de exemplo do estudo (planilha original híbrida + GridZero).

Mantém os datasets de referência separados do orquestrador, para que o pacote
permaneça limpo e os exemplos possam ser importados/executados isoladamente.
"""
from __future__ import annotations

from .LicencaModulos import LicencaModulos
from .InputLoad import InputLoad
from .InputGrid import InputGrid
from .InputSolarSCDEE import InputSolarSCDEE
from .InputBESSPonta import InputBESSPonta
from .ParamsCF import ParamsCF
from .InputGridZero import AnaliseComparativaGridZero, InputGridZero, ResultadoGridZero
from .EstudoViabilidade import EstudoViabilidade


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


def exemplo_gridzero_planilha() -> "dict[float, ResultadoGridZero]":
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


__all__ = ["exemplo_planilha_original", "exemplo_gridzero_planilha"]
