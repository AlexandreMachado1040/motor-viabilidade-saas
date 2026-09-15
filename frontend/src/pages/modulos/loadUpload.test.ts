import { describe, expect, it } from "vitest";
import { dividirLinha, interpretar, lerPlanilha } from "./loadUpload";

describe("interpretar · picos mensais por posto", () => {
  it("guarda a demanda máxima de cada mês por posto, e não a média", () => {
    const rows = [
      ["Data", "Hora", "Postos horários", "Demanda (kW)"],
      ["02/01/2024", "10:00", "Fora Ponta", "50"],
      ["02/01/2024", "11:00", "Fora Ponta", "90"],
      ["02/01/2024", "18:00", "Ponta", "40"],
      ["02/01/2024", "19:00", "Ponta", "70"],
      ["05/02/2024", "18:00", "Ponta", "30"],
    ];
    const r = interpretar(rows);
    expect(r.ok).toBe(true);
    expect(r.picos?.demanda_fp_kw[0]).toBe(90);
    expect(r.picos?.demanda_ponta_kw[0]).toBe(70);
    expect(r.picos?.demanda_ponta_kw[1]).toBe(30);
    expect(r.picos?.demanda_fp_kw[1]).toBe(0); // mês com leitura, só não no posto
    expect(r.picos?.demanda_fp_kw[5]).toBeNull(); // mês sem nenhuma leitura
    expect(r.picos?.demanda_fp_kw).toHaveLength(12);
  });

  it("faz a média dos picos quando o arquivo cobre o mesmo mês em anos diferentes", () => {
    const rows = [
      ["Data", "Hora", "Postos horários", "Demanda (kW)"],
      ["02/03/2023", "10:00", "Fora Ponta", "100"],
      ["02/03/2024", "10:00", "Fora Ponta", "60"],
    ];
    expect(interpretar(rows).picos?.demanda_fp_kw[2]).toBe(80);
  });

  it("não conta como zero o ano em que o posto não tem leitura", () => {
    const rows = [
      ["Data", "Hora", "Postos horários", "Demanda (kW)"],
      ["02/01/2023", "10:00", "Fora Ponta", "100"],
      ["02/01/2024", "18:00", "Ponta", "40"],
    ];
    const r = interpretar(rows);
    expect(r.picos?.demanda_fp_kw[0]).toBe(100);
    expect(r.picos?.demanda_ponta_kw[0]).toBe(40);
  });

  it("aceita coluna Hora numérica 1–24", () => {
    const r = interpretar([
      ["Data", "Hora", "Demanda (kW)"],
      ["02/01/2024", "1", "10"],
      ["02/01/2024", "19", "40"],
      ["02/01/2024", "24", "20"],
    ]);
    expect(r.ok).toBe(true);
    expect(r.payload?.demanda_kw[0][18]).toBe(40); // hora 19 (1–24) = 18h
    expect(r.payload?.demanda_kw[0][23]).toBe(20);
  });
});

describe("dividirLinha", () => {
  it("detecta o delimitador sem contar separador dentro de aspas", async () => {
    const linha = (h: string) => `"02/01/2024";"${h}";"obs: a,b,c,d";"12,5"`;
    const csv = ["Data;Hora;Obs;Demanda (kW)", linha("10:00"), linha("11:00"), linha("12:00")].join("\n");
    const bytes = new TextEncoder().encode(csv);
    // File do jsdom não implementa arrayBuffer().
    const arquivo = { name: "a.csv", arrayBuffer: () => Promise.resolve(bytes.buffer) } as unknown as File;
    const rows = await lerPlanilha(arquivo);
    expect(rows[1]).toEqual(["02/01/2024", "10:00", "obs: a,b,c,d", "12,5"]);
  });

  it("respeita aspas com delimitador e aspas escapadas dentro do campo", () => {
    expect(dividirLinha('"02/01/2024";"18:00";"1.234,56"', ";")).toEqual(["02/01/2024", "18:00", "1.234,56"]);
    expect(dividirLinha('a,"1,5","diz ""oi"""', ",")).toEqual(["a", "1,5", 'diz "oi"']);
  });
});
