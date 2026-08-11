import { defineConfig, devices } from '@playwright/test';
import { personaStorage } from './e2e/helpers/personas';

/**
 * Playwright configuration for Volunteering E2E tests.
 *
 * Setup authenticates all personas into e2e/.auth/<persona>.json.
 * Default chromium project uses Administrator; specs override with:
 *   test.use({ storageState: personaStorage('employee') })
 *
 * @see e2e/helpers/personas.ts
 */
export default defineConfig({
	testDir: './e2e/tests',
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: 1,
	reporter: process.env.CI ? [['github'], ['html']] : 'html',
	timeout: 60000,

	expect: {
		timeout: 10000,
	},

	use: {
		baseURL: process.env.BASE_URL || 'http://sevamrita.local:8000',
		trace: 'on-first-retry',
		video: 'retain-on-failure',
		screenshot: 'only-on-failure',
		actionTimeout: 15000,
		navigationTimeout: 30000,
	},

	projects: [
		{
			name: 'setup',
			testMatch: /auth\.setup\.ts/,
		},
		{
			name: 'chromium',
			use: {
				...devices['Desktop Chrome'],
				storageState: personaStorage('admin'),
			},
			dependencies: ['setup'],
		},
	],
});
