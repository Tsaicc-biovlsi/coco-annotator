import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

// Serve / emit paper.js as a classic (non-module) script, see src/libs/paper-shim.js
const require = createRequire(import.meta.url);
const PAPER_URL = "vendor/paper-core.min.js";
function paperClassicScript() {
  const file = require.resolve("paper/dist/paper-core.min.js");
  return {
    name: "paper-classic-script",
    configureServer(server) {
      server.middlewares.use("/" + PAPER_URL, (req, res) => {
        res.setHeader("Content-Type", "application/javascript");
        res.end(readFileSync(file));
      });
    },
    generateBundle() {
      this.emitFile({ type: "asset", fileName: PAPER_URL, source: readFileSync(file) });
    }
  };
}

// In development the Flask backend runs at BACKEND_URL (docker-compose.dev.yml
// sets it to the "webserver" service); API and websocket calls are proxied.
const backend = process.env.BACKEND_URL || "http://localhost:5000";

export default defineConfig({
  plugins: [vue(), paperClassicScript()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      paper: fileURLToPath(new URL("./src/libs/paper-shim.js", import.meta.url))
    }
  },
  server: {
    host: true,
    port: 8080,
    allowedHosts: true,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      "/socket.io": { target: backend, changeOrigin: true, ws: true }
    }
  },
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 2000
  },
  test: {
    environment: "jsdom"
  }
});
