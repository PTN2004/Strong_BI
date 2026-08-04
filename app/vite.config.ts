import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        secure: false,
      },
      '/login': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/signup': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/logout': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/auth-status': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
