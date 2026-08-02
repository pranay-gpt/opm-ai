// Render-verification harness config: serves frontend/probe/ against the real
// app sources with /api proxied to a local API. Not part of the app build.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: new URL('./probe', import.meta.url).pathname,
  plugins: [react()],
  server: {
    port: 5199,
    proxy: { '/api': { target: 'http://127.0.0.1:8011', changeOrigin: true } },
  },
});
