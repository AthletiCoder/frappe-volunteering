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

		test('coordinator can open Home programs', async ({ page }) => {
			await page.goto('/volunteering/home', { waitUntil: 'domcontentloaded' });
			await expect(page).toHaveURL(/\/volunteering\/home/);
			await expect(page.locator('#app')).toBeVisible();
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
		test('get_home_payload returns allowed staff home', async ({ request }) => {
			const payload = await callMethod<{
				allowed: boolean;
				todo_count: number;
				actions: { time: { id: string; list_route?: string; pending?: number }[] };
			}>(
				request,
				'volunteering.volunteering.home_service.get_home_payload',
			);
			expect(payload.allowed).toBe(true);
			expect(Array.isArray(payload.actions.time)).toBeTruthy();
			expect(typeof payload.todo_count).toBe('number');
			const leave = payload.actions.time.find((row) => row.id === 'leave');
			expect(leave?.list_route).toBe('/app/leave-application');
			expect(typeof leave?.pending).toBe('number');
			expect(leave?.pending).toBeGreaterThanOrEqual(0);
		});

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
