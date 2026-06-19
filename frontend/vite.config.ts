import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Plugin to append ?v=0.0.1 version token to all asset URLs in built HTML
function versionTokenPlugin(): Plugin {
  const VERSION = "0.0.2";
  return {
    name: "version-token",
    enforce: "post",
    transformIndexHtml(html) {
      // Append ?v=VERSION to script src and link href that have /assets/ in path
      return html.replace(
        /(src|href)="(\/projects\/contract-hub\/assets\/[^"]+)"/g,
        `$1="$2?v=${VERSION}"`
      );
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), versionTokenPlugin()],
  base: "/projects/contract-hub/",
  build: {
    outDir: "dist",
    assetsDir: "assets",
  },
  server: {
    port: 5173,
    proxy: {
      "/projects/contract-hub/api": {
        target: "http://localhost:19007",
        changeOrigin: true,
      },
    },
  },
});
