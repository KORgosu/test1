import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    // process.env를 import.meta.env로 매핑
    'process.env': 'import.meta.env'
  },
  server: {
    port: 5173,
    host: true
  }
})
