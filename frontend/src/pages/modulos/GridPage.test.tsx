import type { ContextType } from "react";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EstudoContext } from "../../estudo/EstudoContext";
import type { InputLoadPayload, SimuladorTarifasPayload, SimuladorTarifasResumo } from "../../types";

const api = vi.hoisted(() => ({
  getExemploTarifas: vi.fn(),
  simularTarifas: vi.fn(),
}));
vi.mock("../../api/modulos", () => api);

const config = vi.hoisted(() => ({ DEMO_MODE: false }));
vi.mock("../../config", () => ({
  get DEMO_MODE() { return config.DEMO_MODE; },
  MODULOS: [],
}));

import { GridPage } from "./GridPage";

type EstudoValue = NonNullable<ContextType<typeof EstudoContext>>;

const doze = (v: number) => Array<number>(12).fill(v);

const EXEMPLO: SimuladorTarifasPayload = {
  demanda_ponta_kw: doze(60), demanda_fp_kw: doze(70),
  consumo_ponta_kwh: doze(2000), consumo_fp_kwh: doze(16000),
  demanda_contratada_kw: 60, demanda_contratada_ponta_kw: 60, demanda_contratada_fp_kw: 60,
  tolerancia_ultrapassagem: 0.05, fator_ultrapassagem: 2,
  convencional: { demanda: 30.53, consumo: 0.3242 },
  azul: { demanda_ponta: 28.41, demanda_fp: 10.07, consumo_ponta: 0.44734, consumo_fp: 0.31,
    consumo_ponta_umido: null, consumo_fp_umido: null },
  verde: { demanda: 15.54448, consumo_ponta: 1.75344, consumo_fp: 0.48316,
    consumo_ponta_umido: null, consumo_fp_umido: null },
  baixa_tensao: null,
};

const RESULTADO: SimuladorTarifasResumo = {
  valido: true, erros: [],
  modalidades: [
    { modalidade: "Azul", custo_anual: 106617.98, custo_mensal: doze(8884.83),
      componentes: { "Demanda ponta": 21386.48, "Ultrapassagem ponta": 0 }, ultrapassagem_anual: 3272.83,
      meses_com_ultrapassagem: 7 },
    { modalidade: "Convencional", custo_anual: 103752.09, custo_mensal: doze(8646),
      componentes: { Demanda: 24700.3 }, ultrapassagem_anual: 0, meses_com_ultrapassagem: 0 },
  ],
  recomendada: "Convencional",
  economia_vs_atual: { Convencional: 0, Azul: 2865.89 },
  demandas_sugeridas: [
    { modalidade: "Convencional", demanda_kw: 66.45, demanda_ponta_kw: null, demanda_fp_kw: null,
      custo_anual: 101292.14, economia_anual: 2459.95 },
    { modalidade: "Azul", demanda_kw: null, demanda_ponta_kw: 65.89, demanda_fp_kw: 66.44,
      custo_anual: 105730.7, economia_anual: 887.28 },
  ],
};

const LOAD: InputLoadPayload = {
  demanda_maxima_kw: 120,
  demanda_kw: Array.from({ length: 12 }, () => Array<number>(24).fill(10)),
  energia_ponta_kwh: doze(1111),
  energia_fp_kwh: doze(22222),
};

function renderPagina(load: EstudoValue["load"] = null, extra: Partial<EstudoValue> = {}) {
  const estudo: EstudoValue = {
    load, definirLoad: vi.fn(), limparLoad: vi.fn(),
    tarifas: null, definirTarifas: vi.fn(), limparTarifas: vi.fn(),
    investimentos: {}, definirInvestimento: vi.fn(), limparInvestimento: vi.fn(), ...extra,
  };
  return render(
    <EstudoContext.Provider value={estudo}>
      <MemoryRouter>
        <GridPage />
      </MemoryRouter>
    </EstudoContext.Provider>,
  );
}

beforeEach(() => {
  config.DEMO_MODE = false;
  api.getExemploTarifas.mockReset().mockResolvedValue(EXEMPLO);
  api.simularTarifas.mockReset().mockResolvedValue(RESULTADO);
});

describe("GridPage", () => {
  it("pré-preenche com o exemplo, simula e mostra a recomendada", async () => {
    renderPagina();
    const botao = await screen.findByRole("button", { name: "Simular modalidades" });
    expect(screen.getByText("Exemplo da planilha Simulador de Tarifas")).toBeInTheDocument();
    expect(screen.getByLabelText("Demanda ponta (R$/kW)")).toHaveValue("28.41");

    fireEvent.click(botao);

    expect(await screen.findByText("Modalidade recomendada: Convencional")).toBeInTheDocument();
    expect(screen.getByText(/a menos que Azul/)).toBeInTheDocument();
    expect(screen.getByText("ponta 65,9 kW · fora ponta 66,4 kW")).toBeInTheDocument();
    const payload = api.simularTarifas.mock.calls[0][0] as SimuladorTarifasPayload;
    expect(payload.azul).toEqual({ ...EXEMPLO.azul });
    expect(payload.baixa_tensao).toBeNull();
    expect(payload.tolerancia_ultrapassagem).toBeCloseTo(0.05);
  });

  it("usa consumo e picos da memória de massa do MOD 1", async () => {
    renderPagina({
      payload: LOAD, fonte: "Memória de massa · cliente.csv",
      picos: { demanda_ponta_kw: doze(55), demanda_fp_kw: doze(95) },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Simular modalidades" }));
    await screen.findByText("Modalidade recomendada: Convencional");

    expect(screen.getByText("Memória de massa · cliente.csv")).toBeInTheDocument();
    const payload = api.simularTarifas.mock.calls[0][0] as SimuladorTarifasPayload;
    expect(payload.consumo_fp_kwh).toEqual(doze(22222));
    expect(payload.demanda_fp_kw).toEqual(doze(95));
  });

  it("mês sem leitura no arquivo mantém o valor da tabela e avisa", async () => {
    const picoParcial = [95, 95, null, null, 95, 95, 95, 95, 95, 95, 95, 95];
    renderPagina({
      payload: { ...LOAD, energia_fp_kwh: [22222, 22222, 0, 0, 22222, 22222, 22222, 22222, 22222, 22222, 22222, 22222] },
      fonte: "Memória de massa · parcial.csv",
      picos: { demanda_ponta_kw: picoParcial, demanda_fp_kw: picoParcial },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Simular modalidades" }));
    await screen.findByText("Modalidade recomendada: Convencional");
    expect(screen.getByText(/não tem leituras em Mar, Abr/)).toBeInTheDocument();
    const payload = api.simularTarifas.mock.calls[0][0] as SimuladorTarifasPayload;
    expect(payload.demanda_fp_kw.slice(1, 4)).toEqual([95, 70, 70]);
    expect(payload.consumo_fp_kwh.slice(1, 4)).toEqual([22222, 16000, 16000]);
    expect(EXEMPLO.demanda_fp_kw[2]).toBe(70); // estado original não foi mutado
  });

  it("avisa quando a carga não tem picos e mantém as demandas do exemplo", async () => {
    renderPagina({ payload: LOAD, fonte: "Campanha ANEEL · CEMIG / A4" });
    await screen.findByRole("button", { name: "Simular modalidades" });
    expect(screen.getByText(/Digite as demandas medidas da fatura/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Simular modalidades" }));
    await screen.findByText("Modalidade recomendada: Convencional");
    const payload = api.simularTarifas.mock.calls[0][0] as SimuladorTarifasPayload;
    expect(payload.demanda_fp_kw).toEqual(doze(70));
    expect(payload.consumo_ponta_kwh).toEqual(doze(1111));
  });

  it("edita um mês, aceita vírgula na tarifa e deixa de fora a modalidade desmarcada", async () => {
    renderPagina();
    await screen.findByRole("button", { name: "Simular modalidades" });
    fireEvent.change(screen.getByLabelText("Demanda fora ponta (kW) · Mar"), { target: { value: "88" } });
    fireEvent.change(screen.getByLabelText("Consumo (R$/kWh)", { selector: "#convencional-consumo" }),
      { target: { value: "0,35" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Verde" }));
    fireEvent.click(screen.getByRole("button", { name: "Simular modalidades" }));
    await screen.findByText("Modalidade recomendada: Convencional");

    const payload = api.simularTarifas.mock.calls[0][0] as SimuladorTarifasPayload;
    expect(payload.demanda_fp_kw[2]).toBe(88);
    expect(payload.convencional?.consumo).toBe(0.35);
    expect(payload.verde).toBeNull();
  });

  it("não chama o servidor com tarifa obrigatória vazia", async () => {
    renderPagina();
    await screen.findByRole("button", { name: "Simular modalidades" });
    fireEvent.change(screen.getByLabelText("Demanda ponta (R$/kW)"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Simular modalidades" }));
    expect(await screen.findByText("Azul: informe demanda ponta (r$/kw).")).toBeInTheDocument();
    expect(api.simularTarifas).not.toHaveBeenCalled();
  });

  it("mostra os erros devolvidos pelo motor", async () => {
    api.simularTarifas.mockResolvedValue({ ...RESULTADO, valido: false, erros: ["consumo_fp_kwh não pode ter valor negativo."] });
    renderPagina();
    fireEvent.click(await screen.findByRole("button", { name: "Simular modalidades" }));
    expect(await screen.findByText("consumo_fp_kwh não pode ter valor negativo.")).toBeInTheDocument();
  });

  it("leva ao estudo a modalidade escolhida com o payload simulado", async () => {
    const definirTarifas = vi.fn();
    renderPagina(null, { definirTarifas });
    fireEvent.click(await screen.findByRole("button", { name: "Simular modalidades" }));
    await screen.findByText("Modalidade recomendada: Convencional");

    const select = screen.getByLabelText("Modalidade");
    expect(select).toHaveValue("convencional");
    fireEvent.change(select, { target: { value: "azul" } });
    fireEvent.click(screen.getByRole("button", { name: "Usar no estudo" }));

    expect(definirTarifas).toHaveBeenCalledWith({
      payload: api.simularTarifas.mock.calls[0][0],
      modalidade: "azul", nome: "Azul", custoAnual: 106617.98,
      fonte: "Exemplo da planilha Simulador de Tarifas",
    });
  });

  it("editar depois de simular esconde a opção de usar no estudo", async () => {
    renderPagina();
    fireEvent.click(await screen.findByRole("button", { name: "Simular modalidades" }));
    await screen.findByRole("button", { name: "Usar no estudo" });
    fireEvent.change(screen.getByLabelText("Demanda fora ponta (kW) · Mar"), { target: { value: "88" } });
    expect(screen.queryByRole("button", { name: "Usar no estudo" })).not.toBeInTheDocument();
  });

  it("no modo demonstração avisa e não chama o backend", async () => {
    config.DEMO_MODE = true;
    renderPagina();
    expect(screen.getByText("Indisponível no modo demonstração")).toBeInTheDocument();
    await waitFor(() => expect(api.getExemploTarifas).not.toHaveBeenCalled());
  });
});
