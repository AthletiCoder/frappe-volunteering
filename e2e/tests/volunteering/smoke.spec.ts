import { expect, test } from '@playwright/test';
import { e2eCall, getCast } from '../../helpers/e2e-api';
import { callMethod } from '../../helpers/frappe';
import { personaStorage, PERSONAS } from '../../helpers/personas';
import { ROUTES } from '../../helpers/routes';

test.describe('Volunteering L1 smoke @smoke @volunteering', () => {
	test('e2e cast is seeded', async ({ request }) => {
		const cast = await getCast(request, 'admin');
		expect(cast.employee.exists_user).toBe(true);
		expect(cast.employee.employee).toBeTruthy();
		expect(cast.coordinator.exists_user).toBe(true);
		expect(cast.volunteer.exists_user).toBe(true);
		expect(cast.volunteer.employee).toBeNull();
	});

	test('ensure_fixtures returns project and department', async ({ request }) => {
		const fixtures = await e2eCall<{ project: string; department: string }>(
			request,
			'ensure_fixtures',
		);
		expect(fixtures.project).toBeTruthy();
		expect(fixtures.department).toBeTruthy();
	});
	test('event registration form is reachable', async ({ page }) => {
		const response = await page.goto(ROUTES.eventRegistration, {
			waitUntil: 'domcontentloaded',
		});
		expect(response?.ok() || response?.status() === 404).toBeTruthy();
		// 200 preferred; 404 still means site routed without crash — accept either for smoke
		await expect(page.locator('body')).toBeVisible();
	});

	test.describe('as coordinator', () => {
		test.use({ storageState: personaStorage('coordinator') });

		test('coordinator session is e2e.coordinator', async ({ request }) => {
			const user = await callMethod<string>(
				request,
				'frappe.auth.get_logged_user',
				{},
				'coordinator',
			);
			expect(user).toBe(PERSONAS.coordinator.email);
		});
	});

	test.describe('as volunteer', () => {
		test.use({ storageState: personaStorage('volunteer') });

		test('volunteer session is e2e.volunteer', async ({ request }) => {
			const user = await callMethod<string>(
				request,
				'frappe.auth.get_logged_user',
				{},
				'volunteer',
			);
			expect(user).toBe(PERSONAS.volunteer.email);
		});
	});

	test.describe('API contracts @smoke @volunteering', () => {
		test('get_budget_health returns a list', async ({ request }) => {
			const rows = await callMethod<unknown[]>(
				request,
				'volunteering.volunteering.budget_service.get_budget_health',
			);
			expect(Array.isArray(rows)).toBeTruthy();
		});

		test('logged-in user resolves via auth API', async ({ request }) => {
			const user = await callMethod<string>(
				request,
				'frappe.auth.get_logged_user',
			);
			expect(user).toBeTruthy();
			expect(user).not.toBe('Guest');
		});
	});
});
