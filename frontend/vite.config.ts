import { fileURLToPath } from 'node:url'
import { defineConfig, searchForWorkspaceRoot } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server forwards /api (REST and the /api/v1/ws/live WebSocket) to the FastAPI backend on port 8000.
// The browser therefore talks to a single origin (no CORS), and the same relative URLs work behind one server later.
// The Docs page reads the Markdown guide from ../docs/guide (one source for GitHub and the app), so the dev server
// may also serve files from ../docs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), fileURLToPath(new URL('../docs', import.meta.url))] },
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true },
    },
  },
})