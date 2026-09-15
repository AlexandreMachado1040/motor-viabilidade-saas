import { useContext } from "react";
import { EstudoContext } from "./EstudoContext";

export function useEstudo() {
  const ctx = useContext(EstudoContext);
  if (!ctx) {
    throw new Error("useEstudo deve ser usado dentro de <EstudoProvider>.");
  }
  return ctx;
}
