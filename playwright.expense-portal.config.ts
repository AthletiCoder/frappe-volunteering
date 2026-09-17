import { defineConfig, devices } from "@playwright/test";

// Focused local tests: do not run the full-site fixture seeder.
export default defineConfig({
  testDir: "./e2e/tests/accounts",
  testMatch: "claim-portal.spec.ts",
  outputDir: "./test-results/expense-portal",
  workers: 1,
  reporter: "line",
  timeout: 90000,
  use: {
    ...devices["Desktop Chrome"],
    channel: "chrome",
    baseURL: process.env.BASE_URL || "http://127.0.0.1:8001",
    actionTimeout: 15000,
    screenshot: "only-on-failure",
  },
});
