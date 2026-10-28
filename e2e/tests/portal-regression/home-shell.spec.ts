import { expect, test } from '@playwright/test';
import { loginViaAPI } from '../../helpers/auth';
import { PERSONAS } from '../../helpers/personas';
import { requireLocalRegression } from '../../helpers/portal-regression';

test.beforeEach(({ baseURL }) => requireLocalRegression(baseURL));

test('Home search, own records and forced-light preferences remain available without exposing management', async ({ page }) => {
	await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
	await page.goto('/volunteering/home');
	await expect(page.getByRole('heading', { name: 'Your active projects', exact: true })).toBeVisible();
	await page.getByRole('button', { name: /^Search pages and actions/ }).click();
	const dialog = page.getByRole('dialog', { name: 'Search pages and actions', exact: true });
	await dialog.getByRole('searchbox', { name: 'Search your pages and actions', exact: true }).fill('invoice');
	await expect(dialog.getByRole('link', { name: /Prepare an invoice/ })).toBeVisible();
	await expect(dialog.getByRole('link', { name: /System management|HR management|Chart of Accounts/i })).toHaveCount(0);
	await page.keyboard.press('Escape');
	await page.evaluate(() => localStorage.setItem('volunteering.theme', 'dark'));
	await page.reload();
	await expect(page.locator('html')).not.toHaveClass(/dark/);
	await expect.poll(() => page.evaluate(() => localStorage.getItem('volunteering.theme'))).toBe('light');
	await expect(page.getByRole('button', { name: 'Toggle colour theme' })).toHaveCount(0);
	const nav = page.getByRole('navigation', { name: 'Sections', exact: true });
	const records = nav.locator('details').filter({ has: page.locator('summary').filter({ hasText: 'Time & leave' }) });
	await records.locator('summary').click();
	for (const route of ['/desk/daily-work-log', '/desk/leave-application', '/desk/attendance-request', '/desk/attendance-regularization-request'])
		await expect(records.locator(`a[href="${route}"]`)).toBeVisible();
});

for (const actor of ['manager', 'director', 'chair', 'unpaid', 'coordinator'] as const) {
	test(`${actor} Home retains every server-authorized action without role omissions`, async ({ page }) => {
		await loginViaAPI(page.request, PERSONAS[actor].email, PERSONAS[actor].password);
		const response = page.waitForResponse(response => response.url().includes('get_home_payload'));
		await page.goto('/volunteering/home');
		const data = (await (await response).json()).message;
		await expect(page.locator('main h1')).toHaveText(/^(Home|Your active projects)$/);
		const routes = Object.values(data.actions || {}).flatMap((actions: any) => actions.flatMap((action: any) => [action.route, action.list_route].filter(Boolean)));
		const sidebar = page.getByRole('navigation', { name: 'Sections', exact: true });
		for (const route of routes) await expect(sidebar.locator(`a[href="${route}"]`)).toHaveCount(1);
		if (data.flags.show_member_projects) await expect(page.locator('main h1')).toHaveText('Your active projects');
	});
}

test('Guest cannot retrieve employee, bank, finance or management API data', async ({ request }) => {
	for (const method of [
		'employee_profile.get_my_profile',
		'employee_bank_accounts.get_my_bank_account_summary',
		'chart_of_accounts_portal.get_chart_of_accounts',
		'people_management.get_system_management_workspace',
		'fiscal_year_portal.get_fiscal_year_workspace',
		'vendor_purchases.get_purchase_workspace',
	]) {
		const response = await request.post(`/api/method/volunteering.volunteering.${method}`, { data: {} });
		expect([401, 403], method).toContain(response.status());
	}
});
