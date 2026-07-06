/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies API calls to the FastAPI backend (fontsentry serve).
// The production build is emitted to web/dist and served by that same backend.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test/setup.ts"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text-summary"],
      // Real floor for the pure-logic modules under test (a ratchet, not a
      // snapshot): expand `include` as more modules get unit tests. Components
      // are covered behaviourally (see *.test.tsx), where line % is a weak metric.
      include: [
        "src/lib/privacy.ts",
        "src/lib/url.ts",
        "src/lib/cn.ts",
        "src/lib/findings.ts",
        "src/lib/importSummary.ts",
      ],
      thresholds: { lines: 90, functions: 90, branches: 85, statements: 90 },
    },
  },
});
