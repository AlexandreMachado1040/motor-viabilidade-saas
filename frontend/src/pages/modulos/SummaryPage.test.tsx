import type { ContextType } from "react";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../../auth/AuthContext";
import { EstudoContext } from "../../estudo/EstudoContext";
import type { InputLoadPayload, SummaryResumo } from "../../types";

const api = vi.hoisted(() => ({
  getExemploLoad: vi.fn(),
  getExemploModulo: vi.fn(),
  calcularEstudo: vi.fn(),
}));
vi.mock("../../api/modulos", () => api);

const config = vi.hoisted(() => ({ DEMO_MODE: false }));
vi.mock("../../config", () => ({
  get DEMO_MODE() { return config.DEMO_MODE; },
  MODULOS: [],
}));

import { SummaryPage } from "./SummaryPage";

type AuthValue = NonNullable<ContextType<typeof AuthContext>>;
type EstudoValue = NonNullable<ContextType<typeof EstudoContext>>;

const LOAD_REF: InputLoadPayload = {
  demanda_maxima_kw: 238.56,
  demanda_kw: Array.from({ length: 12 }, () => Array<number>(24).fill(10)),
  energia_ponta_kwh: Array<number>(12).fill(1000),
  energia_fp_kwh: Array<number>(12).fill(2000),
};
const LOAD_USUARIO: InputLoadPayload = { ...LOAD_REF, demanda_maxima_kw: 99 };

const EXEMPLOS: Record<string, Record<string, unknown>> = {
  grid: { concessionaria: "Cemig-D", subgrupo: "A4", modalidade: "Verde" },
  cf: { taxa_desconto: 0.08, anos_projeto: 25 },
  solar: { potencia_cc_kwp: 300, capex_r: 885000 },
  bess_ponta: { energia_dod80_kwh: 1598.05, capex_r: 5526000 },
};

const RESUMO: SummaryResumo = {
  valido: true,
  erros: [],
  projeto: {
    concessionaria: "Cemig-D", subgrupo: "A4", demanda_maxima_kw: 238.56,
    potencia_solar_kwp: 300, energia_bess_kwh: 1598.05,
  },
  custos: { opex_grid_anual: 210064.26, capex_total: 6411000 },
  indicadores: { vpl: -7972861.6, tir_pct: null, payback: null, roi: -1.2436, viavel: false },
  modulos_ativos: { load: true, grid: true, solar: true, bess_ponta: true, cf: true, summary: true },
};

function renderPagina(opts: { licencas?: string[]; load?: EstudoValue["load"] } = {}) {
  const licencas = opts.licencas ?? ["load", "grid", "cf", "solar", "bess_ponta", "summary"];
  const auth = {
    usuario: null, modulos: {}, carregando: false, autenticado: true,
    login: () => {}, loginDev: async () => {}, logout: async () => {}, recarregar: async () => {},
    temModulo: (m: string) => licencas.includes(m),
  } as AuthValue;
  const estudo: EstudoValue = {
    load: opts.load ?? null, definirLoad: vi.fn(), limparLoad: vi.fn(),
  };
  return render(
    <AuthContext.Provider value={auth}>
      <EstudoContext.Provider value={estudo}>
        <MemoryRouter>
          <SummaryPage />
        </MemoryRouter>
      </EstudoContext.Provider>
    </AuthContext.Provider>,
  );
}

beforeEach(() => {
  config.DEMO_MODE = false;
  api.getExemploLoad.mockReset().mockResolvedValue(LOAD_REF);
  api.getExemploModulo.mockReset().mockImplementation((m: string) => Promise.resolve(EXEMPLOS[m]));
  api.calcularEstudo.mockReset().mockResolvedValue(RESUMO);
});

describe("SummaryPage", () => {
  it("calcula o estudo com o cenário de referência e mostra o resultado", async () => {
    renderPagina();
    const botao = await screen.findByRole("button", { name: "Calcular estudo" });
    expect(screen.getByText("Cenário de referência (planilha original)")).toBeInTheDocument();
    expect(screen.getByText("Cemig-D · A4 · Verde")).toBeInTheDocument();

    fireEvent.click(botao);

    expect(await screen.findByText("Estudo não viável")).toBeInTheDocument();
    expect(screen.getByText(/TIR indefinida/)).toBeInTheDocument();
    expect(screen.getByText("Não recupera")).toBeInTheDocument();
    const payload = api.calcularEstudo.mock.calls[0][0];
    expect(payload.load).toEqual(LOAD_REF);
    expect(payload.grid).toEqual(EXEMPLOS.grid);
    expect(payload.params_cf).toEqual(EXEMPLOS.cf);
    expect(payload.solar).toEqual(EXEMPLOS.solar);
    expect(payload.bess_ponta).toEqual(EXEMPLOS.bess_ponta);
  });

  it("usa a carga carregada pelo usuário no MOD 1 e avisa sobre a mistura com a referência", async () => {
    renderPagina({ load: { payload: LOAD_USUARIO, fonte: "Memória de massa · cliente.csv" } });
    const botao = await screen.findByRole("button", { name: "Calcular estudo" });
    expect(screen.getByText("Memória de massa · cliente.csv")).toBeInTheDocument();
    expect(screen.getByText(/não para a sua\s+carga/)).toBeInTheDocument();

    fireEvent.click(botao);
    await screen.findByText("Estudo não viável");
    expect(api.calcularEstudo.mock.calls[0][0].load).toEqual(LOAD_USUARIO);
  });

  it("não envia o investimento desmarcado", async () => {
    renderPagina();
    fireEvent.click(await screen.findByLabelText("BESS de ponta"));
    fireEvent.click(screen.getByRole("button", { name: "Calcular estudo" }));
    await screen.findByText("Estudo não viável");

    const payload = api.calcularEstudo.mock.calls[0][0];
    expect(payload.bess_ponta).toBeNull();
    expect(payload.solar).toEqual(EXEMPLOS.solar);
  });

  it("desabilita o investimento sem licença e não busca o exemplo dele", async () => {
    renderPagina({ licencas: ["load", "grid", "cf", "summary"] });
    const solar = await screen.findByLabelText("Solar (GD / compensação)");
    expect(solar).toBeDisabled();
    expect(screen.getByText("Módulo solar não licenciado")).toBeInTheDocument();
    expect(api.getExemploModulo).not.toHaveBeenCalledWith("solar");
  });

  it("bloqueia o cálculo quando falta a tarifa", async () => {
    renderPagina({ licencas: ["load", "summary"] });
    const botao = await screen.findByRole("button", { name: "Calcular estudo" });
    expect(botao).toBeDisabled();
    expect(screen.getByText(/Falta: tarifas da concessionária/)).toBeInTheDocument();
  });

  it("mostra os erros quando o servidor rejeita os dados", async () => {
    api.calcularEstudo.mockResolvedValue({
      ...RESUMO, valido: false, erros: ["demanda_kw deve ter 12 meses (recebido: 11)."],
    });
    renderPagina();
    fireEvent.click(await screen.findByRole("button", { name: "Calcular estudo" }));
    expect(await screen.findByText("O estudo não pôde ser calculado com estes dados.")).toBeInTheDocument();
    expect(screen.getByText("demanda_kw deve ter 12 meses (recebido: 11).")).toBeInTheDocument();
  });

  it("no modo demonstração avisa que o cálculo é indisponível e não chama o backend", async () => {
    config.DEMO_MODE = true;
    renderPagina();
    expect(screen.getByText("Indisponível no modo demonstração")).toBeInTheDocument();
    await waitFor(() => expect(api.getExemploModulo).not.toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Calcular estudo" })).not.toBeInTheDocument();
  });
});
