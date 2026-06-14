import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: Vite (5173) proxy /api -> backend FastAPI (8000)
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
