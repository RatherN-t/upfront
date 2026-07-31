import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.dirname(fileURLToPath(import.meta.url))

// The API sets an httpOnly session cookie, so the browser must see the API on
// the same origin as the app. Proxying /api in dev avoids the cross-site
// cookie rules that would otherwise silently drop the session.
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8017',
        changeOrigin: true,
      },
    },
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(root, './src'),
    },
  },
})
