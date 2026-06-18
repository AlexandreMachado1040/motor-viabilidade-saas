/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// O backend FastAPI roda em http://localhost:8000 por padrão.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy para a API de dados abertos da ANEEL (CTR – Curva de Carga).
      // A ANEEL não envia CORS; o proxy resolve no dev. Em produção o mesmo
      // caminho /aneel é servido pela Cloudflare Pages Function.
      "/aneel": {
        target: "https://dadosabertos.aneel.gov.br",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/aneel/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
  },
});
