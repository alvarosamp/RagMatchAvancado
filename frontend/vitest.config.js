import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'html'],
      reportsDirectory: 'coverage',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/**/*.test.{js,jsx}'],
      thresholds: {
        'src/utils/authStorage.js': { lines: 90, functions: 90, statements: 90, branches: 80 },
        'src/utils/datetime.js': { lines: 90, functions: 90, statements: 90, branches: 80 },
        'src/utils/themeStorage.js': { lines: 90, functions: 90, statements: 90, branches: 80 },
        'src/pages/Login.jsx': { lines: 80, functions: 75, statements: 80 },
        'src/pages/ForgotPassword.jsx': { lines: 80, functions: 80, statements: 80 },
      },
    },
  },
})
