import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const appVersion = process.env.APP_VERSION ?? 'dev'
const buildNumber = process.env.BUILD_NUMBER ?? 'unknown'

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __APP_BUILD__: JSON.stringify(buildNumber),
  },
  base: '/',
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8088',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist'
  }
})
