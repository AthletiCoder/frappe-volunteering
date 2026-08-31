import { expect, test } from '@playwright/test';
import { isLoggedIn } from '../../helpers/auth';
import { getList } from '../../helpers/frappe';
import { personaStorage } from '../../helpers/personas';
import { DESK_WORKSPACE_RE, ROUTES } from '../../helpers/routes';

test.describe('Ops L1 smoke @smoke @ops', () => {
	test.use({ storageState: personaStorage('admin') });

	test('site ping responds', async ({ request }) => {
		const response = await request.get('/api/method/ping');
		expect(response.ok()).toBeTruthy();
		const body = await response.json();
		expect(body.message).toBe('pong');
	});

	test('authenticated session is not Guest', async ({ request }) => {
		expect(await isLoggedIn(request)).toBeTruthy();
	});

	test('Email Queue is readable via API', async ({ request }) => {
		const rows = await getList(request, 'Email Queue', {
			fields: ['name', 'status'],
			limit: 5,
		});
		expect(Array.isArray(rows)).toBeTruthy();
	});

	test('Email Queue desk list opens', async ({ page }) => {
		await page.goto(ROUTES.emailQueue, { waitUntil: 'domcontentloaded' });
		await expect(page).toHaveURL(DESK_WORKSPACE_RE.emailQueue);
		await expect(
			page.locator('.layout-main, .page-container, #body, .desk-sidebar').first(),
		).toBeVisible({ timeout: 30000 });
	});
});
