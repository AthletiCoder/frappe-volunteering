import { defineConfig, devices } from "@playwright/test";

// Local-only portal checks; shared fixtures are prepared by the main E2E run.
export default defineConfig({
  testDir: "./e2e/tests/advances-portal",
  outputDir: "./test-results/advances-portal",
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
