import { defineConfig, devices } from "@playwright/test";

const baseUse = {
  ...devices["Desktop Chrome"],
  channel: "chrome" as const,
  baseURL: process.env.BASE_URL || "http://127.0.0.1:8001",
  actionTimeout: 15000,
  screenshot: "only-on-failure" as const,
  hasTouch: true,
};

export default defineConfig({
  testDir: "./e2e/tests/mobile",
  outputDir: "./test-results/mobile",
  workers: 1,
  reporter: "line",
  timeout: 90000,
  projects: [
    {
      name: "phone-360",
      use: { ...baseUse, viewport: { width: 360, height: 800 } },
    },
    {
      name: "phone-390",
      use: { ...baseUse, viewport: { width: 390, height: 844 } },
    },
  ],
});
