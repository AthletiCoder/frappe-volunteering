import { expect, test } from '@playwright/test';
import { callMethod } from '../helpers/frappe';
import { personaStorage, PERSONAS } from '../helpers/personas';
import { AdvancesPage } from '../pages/advances.page';
import { ROUTES } from '../helpers/routes';

/**
 * Smoke that multi-persona storageState works (employee → manager).
 * Full spreadsheet flows come later.
 */
test.describe('Multi-persona auth @persona', () => {
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

		test('employee can open Advance Portal', async ({ page }) => {
			const advances = new AdvancesPage(page);
			await advances.goto();
			await advances.expectLoaded();
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
			await page.goto(ROUTES.myWork);
			await page.waitForLoadState('networkidle');
			await expect(page).toHaveURL(/\/(app|desk)\/my-work/);
		});
	});
});
