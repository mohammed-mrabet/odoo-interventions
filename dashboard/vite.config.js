import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En développement, /web (session) et /api sont redirigés vers Odoo :
// le navigateur reste sur la même origine, le cookie de session fonctionne sans CORS.
const ODOO_URL = process.env.ODOO_URL || 'http://localhost:8069'

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 700 },
  server: {
    port: 5173,
    proxy: {
      '/web': { target: ODOO_URL, changeOrigin: true },
      '/api': { target: ODOO_URL, changeOrigin: true },
    },
  },
})
