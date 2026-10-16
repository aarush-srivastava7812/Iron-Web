import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.BACKEND_PROXY_TARGET ?? "http://127.0.0.1:8000";
  return {
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        "/api": backend,
        "/transitions.js": backend,
        "/transitions.css": backend,
      },
    },
  };
});
