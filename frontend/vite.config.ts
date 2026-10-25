import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": new URL("./src", import.meta.url).pathname },
  },
  server: {
    port: 5173,
    // Запросы /api проксируются на бэкенд — CORS в dev не нужен
    proxy: { "/api": "http://localhost:8000" },
  },
});
