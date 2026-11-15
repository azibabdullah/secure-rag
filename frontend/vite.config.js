import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwind()],
  define: { "process.env.NODE_ENV": '"production"' },
  build: {
    lib: {
      entry: "src/main.jsx",
      name: "SecureRAG",
      formats: ["iife"],
      fileName: () => "dashboard.js",
      cssFileName: "style",
    },
    outDir: "dist",
  },
});
