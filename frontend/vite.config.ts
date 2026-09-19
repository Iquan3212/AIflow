import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev-server proxy: the frontend calls relative /api/* paths (see
// services/api.ts's baseURL) so the browser's requests are always
// same-origin - whether the page is loaded at localhost:5174 or through
// a Cloudflare tunnel at some https://*.trycloudflare.com origin, the
// browser only ever talks to whatever host served the page. Vite then
// forwards /api/* server-side to the real FastAPI backend (never a
// browser-to-backend cross-origin request, so backend CORS is a non-
// issue for this path). /api is stripped before forwarding since no
// backend route is actually prefixed with it.
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
    // Vite's dev-server rejects unrecognized Host headers by default (a
    // real DNS-rebinding protection) - a Cloudflare Quick Tunnel's
    // subdomain is random per run, so a fixed hostname can't be listed
    // here; allow only the *.trycloudflare.com suffix (a leading dot
    // means "this suffix", not "any host" - see Vite's allowedHosts
    // docs), never a blanket `true`.
    allowedHosts: [".trycloudflare.com"],
  },
});
