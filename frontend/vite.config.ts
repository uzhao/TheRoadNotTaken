/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 开发时后端默认跑在 127.0.0.1:8000（见 README），/api 请求代理过去。
const BACKEND = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
    },
  },
  // 规格：前端不做组件级单元测试，端到端用例由 Playwright 承担（工单 032）。
  test: {
    passWithNoTests: true,
  },
})
