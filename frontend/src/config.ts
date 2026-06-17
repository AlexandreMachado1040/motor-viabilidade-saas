// Lista canônica de módulos (espelha backend/app/db/models.py: MODULOS).
export const MODULOS = [
  "load", "grid", "solar", "bess_ponta", "gen_ponta", "gen_form",
  "bess_form", "new_grid", "cf", "summary", "gridzero",
];

// Modo demonstração: desabilita o login e faz os módulos rodarem 100% no
// navegador (sem backend). Ativado no build com VITE_DEMO_MODE=true.
// No dev local (npm run dev) fica desligado → login + backend reais.
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";
