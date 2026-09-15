import { describe, expect, it } from "vitest";
import { BESS_PONTA, CF, SOLAR, lerValores, valoresDoPayload } from "./investimentos";

const REF_SOLAR = {
  potencia_cc_kwp: 300, sobrecarga_inversor: 1.42, potencia_ca_kw: 211.27, capex_r: 885000,
  om_anual_r: 1500, degradacao_ano1: 0.02, degradacao_demais: 0.0055, custo_troca_inversor_r: 50000,
  ano_troca_inversor: 12, data_estudo_ano: 2024, modalidade_gd: "GDIII",
  potencia_gerada_kw: [[0, 30, 60]], potencia_injetada_kw: [[0, -30, -60]],
};

const REF_BESS = {
  capex_r: 5526000, custo_reposicao_r: 5526000, tempo_reposicao_anos: 14, vida_util_anos: 14,
  percentual_eol: 0.6, potencia_max_carga_kw: 228.096, potencia_max_descarga_kw: 228.096, eta_total: 0.961,
  energia_dod80_kwh: 1598.05, energia_dod100_kwh: 1997.57, energia_dod80_pos_pcs: 1535.73,
  energia_dod100_pos_pcs: 1919.66, capacidade_c10_ah: 2890, tempo_carga_h: 7.006, tempo_descarga_h: 7.006,
  n_brs: 10,
};

describe("investimentos", () => {
  it("solar escala a geração pela potência e recalcula a potência CA", () => {
    const valores = lerValores(SOLAR, { ...valoresDoPayload(SOLAR, REF_SOLAR), potencia_cc_kwp: "150", sobrecarga_inversor: "1,5" }).valores!;
    const p = SOLAR.montar(REF_SOLAR, valores);
    expect(p.potencia_gerada_kw).toEqual([[0, 15, 30]]);
    expect(p.potencia_injetada_kw).toEqual([[0, -15, -30]]);
    expect(p.potencia_ca_kw).toBe(100);
    expect(p.degradacao_ano1).toBeCloseTo(0.02);
    expect(p.modalidade_gd).toBe("GDIII");
  });

  it("BESS escala energias pela energia útil e recalcula os tempos", () => {
    const tela = { ...valoresDoPayload(BESS_PONTA, REF_BESS), energia_dod80_pos_pcs: "767.865", potencia_max_descarga_kw: "100", potencia_max_carga_kw: "50" };
    const p = BESS_PONTA.montar(REF_BESS, lerValores(BESS_PONTA, tela).valores!);
    expect(p.energia_dod80_kwh).toBeCloseTo(799.025);
    expect(p.energia_dod100_pos_pcs).toBeCloseTo(959.83);
    expect(p.tempo_descarga_h).toBeCloseTo(7.99025);
    expect(p.tempo_carga_h).toBeCloseTo(15.9805);
    expect(p.n_brs).toBe(10); // ficha técnica fica a da referência
  });

  it("percentuais aparecem em % na tela e voltam como fração", () => {
    const tela = valoresDoPayload(CF, { taxa_desconto: 0.08, inflacao: 0.0393, anos_projeto: 25, reajuste_tarifa_ponta: 0.01, reajuste_tarifa_fp: 0, reajuste_demanda_spt: 0.008, reajuste_combustivel: 0.01 });
    expect(tela.taxa_desconto).toBe("8");
    expect(tela.inflacao).toBe("3.93");
    expect(lerValores(CF, tela).valores?.inflacao).toBeCloseTo(0.0393);
  });

  it("rejeita vazio, fora da faixa e inteiro com decimais", () => {
    const tela = { ...valoresDoPayload(CF, { taxa_desconto: 0.08, anos_projeto: 25 }), taxa_desconto: "", anos_projeto: "2.5", inflacao: "150" };
    const { valores, erros } = lerValores(CF, tela);
    expect(valores).toBeUndefined();
    expect(erros).toContain("Informe taxa de desconto (nominal).");
    expect(erros).toContain("Horizonte deve ser um número inteiro.");
    expect(erros).toContain("Inflação: fora da faixa (mínimo 0, máximo 100).");
  });
});
