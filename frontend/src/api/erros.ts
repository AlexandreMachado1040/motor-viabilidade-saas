import { isAxiosError } from "axios";

/** Mensagem legível para falhas de chamada ao backend dos módulos. */
export function mensagemDeErro(e: unknown, padrao: string): string {
  if (isAxiosError(e)) {
    const detail = (e.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return "Os dados enviados não passaram na validação do servidor.";
    }
    if (!e.response) return "Sem resposta do servidor. Verifique se o backend está rodando.";
  }
  return padrao;
}
