import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/dashboard': { target: 'http://localhost:8080', changeOrigin: true },
      '/ingest':    { target: 'http://localhost:8080', changeOrigin: true },
      '/session':   { target: 'http://localhost:8080', changeOrigin: true },
      '/concepts':  { target: 'http://localhost:8080', changeOrigin: true },
      '/graph':     { target: 'http://localhost:8080', changeOrigin: true },
      '/health':    { target: 'http://localhost:8080', changeOrigin: true },
      '/chat':      { target: 'http://localhost:8080', changeOrigin: true },
    },
  },
});
