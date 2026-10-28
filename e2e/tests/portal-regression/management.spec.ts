import { expect, test, type Page } from '@playwright/test';
import { loginViaAPI } from '../../helpers/auth';
import { PERSONAS } from '../../helpers/personas';
import { expectNoDesk, portalCall, requireLocalRegression } from '../../helpers/portal-regression';

async function signIn(page: Page, actor: keyof typeof PERSONAS, route: string) {
	await page.context().clearCookies();
	await loginViaAPI(page.request, PERSONAS[actor].email, PERSONAS[actor].password);
	await page.goto(route);
	await expectNoDesk(page);
}
test.beforeEach(({ baseURL }) => requireLocalRegression(baseURL));

test('System creates a login; HR links and edits its employee; System can reset and disable it', async ({ page }) => {
	test.setTimeout(150_000);
	const suffix = Date.now();
	const email = `qa-home-person-${suffix}@example.com`;
	await signIn(page, 'admin', '/volunteering/system-management');
	await page.getByRole('button', { name: 'Add user', exact: true }).click();
	await page.getByLabel('Email / User ID *', { exact: true }).fill(email);
	await page.getByLabel('First name *', { exact: true }).fill('Arjun');
	await page.getByLabel('Last name', { exact: true }).fill(`QA${suffix}`);
	await page.getByRole('checkbox', { name: /Send welcome email/ }).uncheck();
	await page.getByLabel('Find a role').fill('Expense Approver');
	await page.locator('.option-row').filter({ hasText: 'Expense Approver' }).getByRole('checkbox').check();
	const created = page.waitForResponse(response => response.url().includes('save_managed_user'));
	await page.getByRole('button', { name: 'Save user and access', exact: true }).click();
	const createdResponse = await created;
	expect(createdResponse.status(), await createdResponse.text()).toBe(200);
	await expect(page.getByRole('status')).toContainText('was saved');
	const user = (await createdResponse.json()).message.user;
	expect(user.name).toBe(email);
	expect(user.roles).toContain('Expense Approver');

	await signIn(page, 'hr', '/volunteering/hr-management');
	await page.getByRole('button', { name: 'Add employee', exact: true }).click();
	await page.getByLabel('First name *', { exact: true }).fill('Arjun');
	await page.getByLabel('Last name', { exact: true }).fill(`QA${suffix}`);
	await page.getByRole('combobox', { name: 'Gender *', exact: true }).selectOption('Male');
	await page.getByLabel('Date of birth *', { exact: true }).fill('1996-05-12');
	await page.getByLabel('Date of joining *', { exact: true }).fill('2026-04-01');
	await page.getByRole('combobox', { name: /^Linked User account/ }).selectOption(email);
	await page.getByRole('combobox', { name: /^Grade/ }).selectOption('Associate');
	const saved = page.waitForResponse(response => response.url().includes('save_managed_employee'));
	await page.getByRole('button', { name: 'Save employee', exact: true }).click();
	const savedResponse = await saved;
	expect(savedResponse.status(), await savedResponse.text()).toBe(200);
	const employee = (await savedResponse.json()).message.employee;
	expect(employee.user_id).toBe(email);
	await page.getByRole('textbox', { name: 'Mobile', exact: true }).fill('9876543210');
	await page.getByRole('button', { name: 'Save employee', exact: true }).click();
	await expect(page.getByRole('status')).toContainText('was saved');
	await page.reload();
	await page.getByLabel('Find an employee').fill(employee.name);
	await page.locator('.directory-card').filter({ hasText: employee.name }).click();
	await expect(page.getByRole('textbox', { name: 'Mobile', exact: true })).toHaveValue('9876543210');

	await signIn(page, 'admin', '/volunteering/system-management');
	await page.getByLabel('Find a user').fill(email);
	await page.locator('.directory-card').filter({ hasText: email }).click();
	const linked = await portalCall(page, 'volunteering.volunteering.people_management.get_managed_user', { name: email });
	expect(linked.employee.name).toBe(employee.name);
	expect(linked.roles).toContain('Employee');
	await page.getByLabel('First name *', { exact: true }).fill('Arjun Pending');
	page.once('dialog', dialog => dialog.accept());
	const reset = page.waitForResponse(response => response.url().includes('send_managed_user_password_reset'));
	await page.getByRole('button', { name: 'Reset password', exact: true }).click();
	const resetResponse = await reset;
	expect(resetResponse.status(), await resetResponse.text()).toBe(200);
	expect(JSON.stringify((await resetResponse.json()).message)).not.toMatch(/reset_password_key|reset_password\?/);
	await expect(page.getByRole('status')).toContainText('A password reset link was sent');
	await expect(page.getByLabel('First name *', { exact: true })).toHaveValue('Arjun Pending');
	await page.getByRole('checkbox', { name: /^Enabled/ }).uncheck();
	await page.getByRole('button', { name: 'Save user and access', exact: true }).click();
	await expect(page.getByRole('status')).toContainText('was saved');
	await expect(page.getByRole('button', { name: 'Reset password', exact: true })).toBeDisabled();
	const finalUser = await portalCall(page, 'volunteering.volunteering.people_management.get_managed_user', { name: email });
	expect(finalUser.enabled).toBeFalsy();
	expect(finalUser.first_name).toBe('Arjun Pending');
});

test('ordinary employees and HR cannot use System/Fiscal administration endpoints', async ({ page }) => {
	for (const [actor, route, message] of [
		['employee', '/volunteering/hr-management', /HR Manager|Administrator/],
		['employee', '/volunteering/system-management', /System Manager|Administrator/],
		['hr', '/volunteering/system-management', /System Manager|Administrator/],
		['accounts', '/volunteering/fiscal-years', /System Manager|Administrator/],
	] as const) {
		await signIn(page, actor, route);
		await expect(page.getByRole('alert')).toContainText(message);
		await expect(page.locator('.directory-card')).toHaveCount(0);
	}
});

test('System adds and reactivates a fiscal year without closing existing years', async ({ page }) => {
	await signIn(page, 'admin', '/volunteering/fiscal-years');
	await expect(page.getByRole('heading', { name: 'Fiscal years', exact: true })).toBeVisible();
	const api = 'volunteering.volunteering.fiscal_year_portal.';
	const before = await portalCall(page, `${api}get_fiscal_year_workspace`);
	const year = Array.from({ length: 30 }, (_, index) => 2050 + index).find(value => !before.years.some((row: any) => row.name === `${value}-${value + 1}`))!;
	expect(year).toBeTruthy();
	const name = `${year}-${year + 1}`;
	await page.getByLabel('Starting year *').fill(String(year));
	page.once('dialog', dialog => dialog.accept());
	await page.getByRole('button', { name: 'Create fiscal year', exact: true }).click();
	await expect(page.getByRole('status')).toContainText(`FY ${name} is active`);
	const after = await portalCall(page, `${api}get_fiscal_year_workspace`);
	for (const row of before.years.filter((value: any) => value.active))
		expect(after.years.find((value: any) => value.name === row.name)?.active).toBeTruthy();
	await portalCall(page, 'frappe.client.set_value', { doctype: 'Fiscal Year', name, fieldname: 'disabled', value: 1 });
	await page.reload();
	const row = page.locator('.year-row').filter({ has: page.getByRole('heading', { name: `FY ${name}`, exact: true }) });
	await expect(row).toContainText('Disabled');
	page.once('dialog', dialog => dialog.accept());
	await row.getByRole('button', { name: 'Reactivate', exact: true }).click();
	await expect(row).toContainText('Active');
	await expect(row.getByRole('button', { name: 'Reactivate', exact: true })).toHaveCount(0);
});
