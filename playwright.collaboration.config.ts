import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.COLLABORATION_TEST_URL || 'http://127.0.0.1:8002';
const url = new URL(baseURL);
if (!['127.0.0.1', 'localhost'].includes(url.hostname) || url.port !== '8002') {
    throw new Error('Collaboration writes run only against the isolated regression server on localhost:8002.');
}

export default defineConfig({
    testDir: './e2e/tests/portal-regression',
    testMatch: 'collaboration.spec.ts',
    outputDir: './test-results/collaboration-isolated',
    workers: 1,
    reporter: [['line'], ['json', { outputFile: 'test-results/collaboration-isolated-results.json' }]],
    timeout: 90000,
    use: { ...devices['Desktop Chrome'], channel: 'chrome', baseURL, actionTimeout: 15000, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
});
