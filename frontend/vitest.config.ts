import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    exclude: ["**/node_modules/**", "**/dist/**", "e2e/**"],
    // Node >=25 enables a native `localStorage` global by default, which
    // throws without --localstorage-file and shadows jsdom's own
    // window.localStorage before the jsdom environment can install it.
    // Disable Node's built-in implementation so jsdom's wins.
    execArgv: ["--no-experimental-webstorage"],
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
});
