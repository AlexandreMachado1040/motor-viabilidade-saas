import { beforeEach, describe, expect, it } from "vitest";

import { getAccessToken, setAccessToken } from "./client";

describe("store de access token do cliente HTTP", () => {
  beforeEach(() => setAccessToken(null));

  it("começa sem token em memória", () => {
    expect(getAccessToken()).toBeNull();
  });

  it("armazena e devolve o token definido", () => {
    setAccessToken("jwt.de.teste");
    expect(getAccessToken()).toBe("jwt.de.teste");
  });

  it("limpa o token ao definir null (logout)", () => {
    setAccessToken("jwt.de.teste");
    setAccessToken(null);
    expect(getAccessToken()).toBeNull();
  });
});
