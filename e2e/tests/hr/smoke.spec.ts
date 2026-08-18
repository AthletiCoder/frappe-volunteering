import { expect, test } from '@playwright/test';
import { callMethod } from '../../helpers/frappe';
import { personaStorage, PERSONAS } from '../../helpers/personas';
import { ROUTES } from '../../helpers/routes';
import { HomePage } from '../../pages/home.page';

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

		test('HR-DWL-013: Home loads for employee', async ({ page }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
			await expect(page.getByText('Time')).toBeVisible();
			await expect(page.getByRole('link', { name: 'Apply for leave' })).toBeVisible();
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

		test('manager can open Home', async ({ page }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
		});
	});
});
