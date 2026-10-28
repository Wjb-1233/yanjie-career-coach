import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'apk-download-headers',
      configurePreviewServer(server) {
        server.middlewares.use((request, response, next) => {
          if ((request as typeof request & { url?: string }).url?.split('?')[0] === '/downloads/yanjie-android-test.apk') {
            response.setHeader('Content-Type', 'application/vnd.android.package-archive')
            response.setHeader('Content-Disposition', 'attachment; filename="yanjie-android-test.apk"')
          }
          next()
        })
      },
    },
  ],
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
      '/api': 'http://127.0.0.1:8081',
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8081',
    },
  },
})

