/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    exclude: ['**/node_modules/**', '**/dist/**', '**/tests/e2e/**'], // Exclude E2E tests
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      // Write the report even when a test fails (e.g. the known
      // MealPlanFilter timing flake that only trips under coverage load).
      reportOnFailure: true,
      include: ['src/**/*.{js,jsx}'],
      // Test helpers and the app entry point are not application code.
      exclude: ['src/test/**', 'src/main.jsx', '**/*.test.{js,jsx}'],
    },
  },
})
