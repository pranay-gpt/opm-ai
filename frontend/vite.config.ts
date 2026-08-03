import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Split the three big vendors out of the app chunk. They change far
        // less often than app code, so a rebuild no longer invalidates the
        // whole 5.8 MB bundle in every browser cache. Pure output grouping:
        // the same modules load in the same order, just from more files.
        manualChunks: {
          three: ['three'],
          plotly: ['plotly.js-dist-min'],
          monaco: ['@monaco-editor/react'],
        },
      },
    },
  },
})