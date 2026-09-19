import "./e2e/playwright-env";
import { defineConfig, devices } from "@playwright/test";

// Run after the full suite, against its prepared local demo personas.
export default defineConfig({
  testDir: "./e2e/tests",
  testMatch: [/advances-portal\/.*\.spec\.ts$/, /release\/.*\.spec\.ts$/],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180000,
  expect: { timeout: 15000 },
  reporter: [["line"]],
  use: {
    baseURL: process.env.BASE_URL || "http://127.0.0.1:8001",
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
  ],
});
