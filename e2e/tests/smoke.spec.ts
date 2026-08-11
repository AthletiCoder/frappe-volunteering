import { expect, test } from '@playwright/test';
import { isLoggedIn } from '../helpers/auth';
import { ROUTES } from '../helpers/routes';

test.describe('Ops smoke @smoke', () => {
	test('site ping responds', async ({ request }) => {
		const response = await request.get('/api/method/ping');
		expect(response.ok()).toBeTruthy();
		const body = await response.json();
		expect(body.message).toBe('pong');
	});

	test('authenticated session is not Guest', async ({ request }) => {
		expect(await isLoggedIn(request)).toBeTruthy();
	});

	test('Budget Health SPA mounts', async ({ page }) => {
		await page.goto(ROUTES.budgetHealth);
		await page.waitForLoadState('networkidle');
		await expect(page.locator('#app')).toBeVisible();
		await expect(
			page.getByRole('heading', { name: 'Budget Health', level: 1 }),
		).toBeVisible({ timeout: 30000 });
	});

	test('Advance Portal SPA mounts', async ({ page }) => {
		await page.goto(ROUTES.advances);
		await page.waitForLoadState('networkidle');
		await expect(page.locator('#app')).toBeVisible();
		await expect(
			page.getByRole('heading', { name: 'Advance Portal', level: 1 }),
		).toBeVisible({ timeout: 30000 });
	});
});
