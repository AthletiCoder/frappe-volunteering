import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.BASE_URL || "http://127.0.0.1:8001";
const reportName = process.env.PORTAL_REPORT_NAME || "portal-regression";
if (!/^[a-z0-9-]+$/.test(reportName)) throw new Error("Use a simple report name.");
if (!["127.0.0.1", "localhost", "sevamrita.local"].includes(new URL(baseURL).hostname)) {
  throw new Error("The complete portal regression suite is restricted to the local demo site.");
}

export default defineConfig({
  testDir: "./e2e/tests",
  testMatch: [
    "**/projects/*.spec.ts",
    "**/advances-portal/*.spec.ts",
    "**/accounts/claim-portal.spec.ts",
    "**/bank-accounts/*.spec.ts",
    "**/profile/*.spec.ts",
    "**/portal-regression/*.spec.ts",
    "**/release/expense-lifecycle.spec.ts",
  ],
  // Kept as a separate legacy suite, not part of the Home release gate.
  testIgnore: "**/projects/layout.spec.ts",
  outputDir: `./test-results/${reportName}`,
  workers: 1,
  reporter: [
    ["line"],
    ["json", { outputFile: `test-results/${reportName}-results.json` }],
    ["html", { outputFolder: `test-results/${reportName}-report`, open: "never" }],
  ],
  timeout: 90000,
  use: {
    ...devices["Desktop Chrome"],
    channel: "chrome",
    baseURL,
    actionTimeout: 15000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
