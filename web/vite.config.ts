import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const TARGET = process.env.CLIPPER_API ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": { target: TARGET, changeOrigin: true },
      "/ws": { target: TARGET, ws: true, changeOrigin: true },
      "/media": { target: TARGET, changeOrigin: true },
    },
  },
  preview: {
    port: 4173,
  },
});
