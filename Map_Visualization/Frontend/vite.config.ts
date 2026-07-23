import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    watch: {
      // Avoid watching the very large runtime dataset to prevent file-lock and memory issues
      ignored: ['**/public/data/points_all_years.json'],
    },
  },
})
