import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  // Never inline assets as data: URIs; the Content-Security-Policy only allows files from the same origin.
  build: { assetsInlineLimit: () => false },
  server: { port: 5173, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8000', '/auth': 'http://127.0.0.1:8000' } },
});
