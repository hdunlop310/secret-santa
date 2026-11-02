import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end test against a running stack: Postgres, Mailpit, the API on :8000 and the
 * app on :5173 (`make dev`). Personal links are read from Mailpit, so the API must use
 * EMAIL_BACKEND=smtp. Locally the servers you already run are reused; in CI they start here.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    ...devices['Pixel 7'],
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'uv --directory ../backend run uvicorn app.main:app --port 8000',
      url: 'http://localhost:8000/health',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
