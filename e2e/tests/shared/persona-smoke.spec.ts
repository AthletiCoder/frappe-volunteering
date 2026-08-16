import { expect, test } from '@playwright/test';
import { callMethod } from '../../helpers/frappe';
import { personaStorage, PERSONAS } from '../../helpers/personas';
import { AdvancesPage } from '../../pages/advances.page';

/**
 * Cross-module multi-persona check (employee + manager storageState).
 */
test.describe('Shared persona smoke @smoke @persona', () => {
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
	});

	test.describe('as chair (Board of Directors grade)', () => {
		test.use({ storageState: personaStorage('chair') });

		test('chair session is e2e.chair', async ({ request }) => {
			const user = await callMethod<string>(
				request,
				'frappe.auth.get_logged_user',
				{},
				'chair',
			);
			expect(user).toBe(PERSONAS.chair.email);
		});
	});
});
