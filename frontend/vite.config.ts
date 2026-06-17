import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',   // Listen on localhost only (not 0.0.0.0)
    port: 5173,
    proxy: {
      // Optional: proxy /api calls to avoid CORS in dev
      // '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,   // No source maps in production (security)
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
        }
      }
    }
  }
})
