import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: resolve(__dirname, "src/main.tsx"),
      name: "MaintainersCopilot",
      fileName: "widget",
      formats: ["iife"],
    },
    rollupOptions: {
      // Bundle React inline — no external deps for single-file embed
      external: [],
    },
    outDir: "../public",
    emptyOutDir: false,
  },
});
