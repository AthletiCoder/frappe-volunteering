import { defineConfig, devices } from "@playwright/test";

// Read-only profile checks and logout in isolated browser sessions. No seeder.
export default defineConfig({
  testDir: "./e2e/tests/profile",
  outputDir: "./test-results/profile",
  workers: 1,
  reporter: "line",
  timeout: 60000,
  use: {
    ...devices["Desktop Chrome"],
    channel: "chrome",
    baseURL: process.env.BASE_URL || "http://127.0.0.1:8001",
    actionTimeout: 15000,
    screenshot: "only-on-failure",
  },
});
