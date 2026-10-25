import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    // Запросы /api проксируются на бэкенд — CORS в dev не нужен
    proxy: { "/api": "http://localhost:8000" },
  },
});
