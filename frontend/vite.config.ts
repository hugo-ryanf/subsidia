import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";
const rotas = ["/health", "/processos", "/jobs", "/demo", "/rh"];

export default defineConfig({
  plugins: [react()],
  server: { proxy: Object.fromEntries(rotas.map((r) => [r, api])) },
});
