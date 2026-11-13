import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server forwards /api (REST and the /api/v1/ws/live WebSocket) to the FastAPI backend on port 8000.
// The browser therefore talks to a single origin (no CORS), and the same relative URLs work behind one server later.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true },
    },
  },
})