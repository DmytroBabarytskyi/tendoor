import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// У режимі розробки /api проксіюється на бекенд (uv run uvicorn … :8000)
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
