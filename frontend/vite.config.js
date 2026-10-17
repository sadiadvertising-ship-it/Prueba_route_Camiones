import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    // The setup file sets the process time zone, which only holds when tests run in forks.
    pool: 'forks',
  },
})
