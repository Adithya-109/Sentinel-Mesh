import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the console API. 127.0.0.1, never "localhost": on this
// Windows machine localhost resolves to ::1 first and stalls ~2 s per request, and the
// UI polls every second (see console/api/config.py). In production the console API
// serves the built app from web/dist at /, same origin, so no proxy is involved.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist", chunkSizeWarningLimit: 1200 },
});
