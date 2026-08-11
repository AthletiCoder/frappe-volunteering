import { expect, test } from '@playwright/test';
import { callMethod } from '../../helpers/frappe';

test.describe('Volunteering API contracts', () => {
	test('get_budget_health returns a list', async ({ request }) => {
		const rows = await callMethod<unknown[]>(
			request,
			'volunteering.volunteering.budget_service.get_budget_health',
		);
		expect(Array.isArray(rows)).toBeTruthy();
	});

	test('get_my_advances returns advances payload (or Employee link error)', async ({
		request,
	}) => {
		try {
			const data = await callMethod<{ advances?: unknown[] }>(
				request,
				'volunteering.volunteering.advance_portal.get_my_advances',
			);
			expect(Array.isArray(data.advances ?? [])).toBeTruthy();
		} catch (error) {
			const blob = String(error).toLowerCase();
			expect(blob).toMatch(/employee/);
		}
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
