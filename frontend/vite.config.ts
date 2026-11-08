import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue(),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('markdown-it') || id.includes('dompurify')) return 'vendor-markdown'
          if (id.includes('reka-ui') || id.includes('lucide')) return 'vendor-ui'
          if (id.includes('axios')) return 'vendor-http'
          if (id.includes('vue') || id.includes('@vue')) return 'vendor-vue'
          return undefined
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8081', ws: true },
      '/media': 'http://127.0.0.1:8081',
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8081', ws: true },
      '/media': 'http://127.0.0.1:8081',
    },
  },
})

