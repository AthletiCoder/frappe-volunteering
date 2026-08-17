import { expect, test } from '@playwright/test';
import { callMethod } from '../../helpers/frappe';
import { personaStorage, PERSONAS } from '../../helpers/personas';
import { DESK_WORKSPACE_RE, ROUTES } from '../../helpers/routes';

test.describe('HR L1 smoke @smoke @hr', () => {
	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('employee session is e2e.employee', async ({ request }) => {
			const user = await callMethod<string>(
				request,
				'frappe.auth.get_logged_user',
				{},
				'employee',
			);
			expect(user).toBe(PERSONAS.employee.email);
		});

		test('HR-DWL-013: My Work hub loads for employee', async ({ page }) => {
			await page.goto(ROUTES.myWork, { waitUntil: 'domcontentloaded' });
			await expect(page).toHaveURL(DESK_WORKSPACE_RE.myWork);
			await expect(
				page.locator('.layout-main, .page-container, #body, .desk-sidebar').first(),
			).toBeVisible({ timeout: 30000 });
		});
	});

	test.describe('as manager', () => {
		test.use({ storageState: personaStorage('manager') });

		test('manager session is e2e.manager', async ({ request }) => {
			const user = await callMethod<string>(
				request,
				'frappe.auth.get_logged_user',
				{},
				'manager',
			);
			expect(user).toBe(PERSONAS.manager.email);
		});

		test('manager can open My Work', async ({ page }) => {
			await page.goto(ROUTES.myWork, { waitUntil: 'domcontentloaded' });
			await expect(page).toHaveURL(DESK_WORKSPACE_RE.myWork);
		});
	});
});
