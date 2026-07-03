import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Docker Compose 裡前端要打 "backend" 這個 service 名稱，本機開發則是 localhost
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8000";
const apiProxy = {
  "/api": {
    target: apiProxyTarget,
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: apiProxy,
  },
  preview: {
    port: 4173,
    proxy: apiProxy,
  },
});
