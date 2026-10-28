import { defineConfig, devices } from '@playwright/test';

// Browser interaction tests use deterministic API contracts. The matching
// Python integration tests exercise real ERP documents and their ledger entries.
export default defineConfig({
	testDir: './e2e/tests/purchasing',
	workers: 1,
	reporter: 'line',
	outputDir: './test-results/purchasing-ui',
	timeout: 45000,
	use: { ...devices['Desktop Chrome'], channel: 'chrome', baseURL: 'http://127.0.0.1:8081', screenshot: 'only-on-failure' },
	webServer: {
		command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 8081 --strictPort',
		cwd: './frontend', url: 'http://127.0.0.1:8081', reuseExistingServer: false,
	},
});
