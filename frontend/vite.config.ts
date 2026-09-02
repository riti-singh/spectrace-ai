import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/dashboard/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/requirements": "http://127.0.0.1:8000",
      "/components": "http://127.0.0.1:8000",
      "/risks": "http://127.0.0.1:8000",
      "/test-cases": "http://127.0.0.1:8000",
      "/traceability": "http://127.0.0.1:8000",
      "/retrieval": "http://127.0.0.1:8000",
      "/graph": "http://127.0.0.1:8000"
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true
  }
});
