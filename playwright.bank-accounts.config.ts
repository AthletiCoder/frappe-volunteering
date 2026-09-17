import { defineConfig, devices } from "@playwright/test";

// Opt-in local demo suite, without the full-site seeder.
export default defineConfig({
  testDir: "./e2e/tests/bank-accounts",
  outputDir: "./test-results/bank-accounts",
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
