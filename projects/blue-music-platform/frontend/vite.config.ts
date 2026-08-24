import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const apiProxy = {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: false,
  },
}

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['.trycloudflare.com'],
    proxy: apiProxy,
  },
  preview: {
    allowedHosts: ['.trycloudflare.com'],
    proxy: apiProxy,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
