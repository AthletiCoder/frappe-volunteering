import { defineConfig, devices } from "@playwright/test";

// Deliberately opt-in: no full seeder, no writes outside the local demo project.
process.env.E2E_PROJECT_DEMOS = "1";
export default defineConfig({
  testDir: "./e2e/tests/projects",
  testMatch: ["workspace.spec.ts", "layout.spec.ts"],
  outputDir: "./test-results/project-workspace",
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
