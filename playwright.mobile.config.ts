import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.BASE_URL || "http://127.0.0.1:8002";
if (!["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname) || new URL(baseURL).port !== "8002")
  throw new Error("The mobile portal regression suite requires the isolated localhost:8002 database.");

const baseUse = {
  ...devices["Desktop Chrome"],
  channel: "chrome" as const,
  baseURL,
  actionTimeout: 15000,
  screenshot: "only-on-failure" as const,
  hasTouch: true,
};

export default defineConfig({
  testDir: "./e2e/tests/mobile",
  outputDir: "./test-results/mobile",
  workers: 1,
  reporter: [["line"], ["json", { outputFile: "test-results/mobile-results.json" }]],
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
