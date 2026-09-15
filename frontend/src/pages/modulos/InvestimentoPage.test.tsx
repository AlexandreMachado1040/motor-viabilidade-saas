import type { ContextType } from "react";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EstudoContext } from "../../estudo/EstudoContext";

const api = vi.hoisted(() => ({ getExemploModulo: vi.fn(), validarModulo: vi.fn() }));
vi.mock("../../api/modulos", () => api);

const config = vi.hoisted(() => ({ DEMO_MODE: false }));
vi.mock("../../config", () => ({
  get DEMO_MODE() { return config.DEMO_MODE; },
  MODULOS: [],
}));

import { InvestimentoPage } from "./InvestimentoPage";
import { CF } from "./investimentos";

type EstudoValue = NonNullable<ContextType<typeof EstudoContext>>;

const REF_CF = {
  taxa_desconto: 0.08, inflacao: 0.0393, anos_projeto: 25, reajuste_tarifa_ponta: 0.01,
  reajuste_tarifa_fp: 0, reajuste_demanda_spt: 0.008, reajuste_combustivel: 0.01,
};

function renderPagina(extra: Partial<EstudoValue> = {}) {
  const estudo: EstudoValue = {
    load: null, definirLoad: vi.fn(), limparLoad: vi.fn(),
    tarifas: null, definirTarifas: vi.fn(), limparTarifas: vi.fn(),
    investimentos: {}, definirInvestimento: vi.fn(), limparInvestimento: vi.fn(), ...extra,
  };
  render(
    <EstudoContext.Provider value={estudo}>
      <MemoryRouter>
        <InvestimentoPage cfg={CF} />
      </MemoryRouter>
    </EstudoContext.Provider>,
  );
  return estudo;
}

beforeEach(() => {
  config.DEMO_MODE = false;
  api.getExemploModulo.mockReset().mockResolvedValue(REF_CF);
  api.validarModulo.mockReset().mockResolvedValue({ valido: true, erros: [] });
});

describe("InvestimentoPage", () => {
  it("pré-preenche com a referência, valida no servidor e salva no estudo", async () => {
    const estudo = renderPagina();
    const taxa = await screen.findByLabelText("Taxa de desconto (nominal) (%)");
    expect(taxa).toHaveValue("8");
    expect(screen.getByText("dados de referência")).toBeInTheDocument();

    fireEvent.change(taxa, { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar no estudo" }));

    await screen.findByText(/Salvo no estudo/);
    const esperado = { ...REF_CF, taxa_desconto: 0.12 };
    expect(api.validarModulo).toHaveBeenCalledWith("cf", esperado);
    expect(estudo.definirInvestimento).toHaveBeenCalledWith("cf", esperado);
  });

  it("abre com o que já foi salvo e permite voltar à referência", async () => {
    const estudo = renderPagina({ investimentos: { cf: { ...REF_CF, anos_projeto: 10 } } });
    expect(await screen.findByLabelText("Horizonte (anos)")).toHaveValue("10");
    expect(screen.getByText("valores personalizados")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Voltar aos dados de referência" }));
    expect(estudo.limparInvestimento).toHaveBeenCalledWith("cf");
    expect(screen.getByLabelText("Horizonte (anos)")).toHaveValue("25");
  });

  it("não salva quando a tela ou o servidor rejeitam", async () => {
    const estudo = renderPagina();
    const anos = await screen.findByLabelText("Horizonte (anos)");
    fireEvent.change(anos, { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar no estudo" }));
    expect(await screen.findByText("Horizonte: fora da faixa (mínimo 1, máximo 50).")).toBeInTheDocument();
    expect(api.validarModulo).not.toHaveBeenCalled();

    api.validarModulo.mockResolvedValue({ valido: false, erros: ["taxa inválida"] });
    fireEvent.change(anos, { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar no estudo" }));
    expect(await screen.findByText("taxa inválida")).toBeInTheDocument();
    expect(estudo.definirInvestimento).not.toHaveBeenCalled();
  });

  it("no modo demonstração avisa e não chama o backend", async () => {
    config.DEMO_MODE = true;
    renderPagina();
    expect(screen.getByText("Indisponível no modo demonstração")).toBeInTheDocument();
    await waitFor(() => expect(api.getExemploModulo).not.toHaveBeenCalled());
  });
});
