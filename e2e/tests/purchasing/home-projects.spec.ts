import { expect, test } from '@playwright/test';

const project = {
	name: 'PROJ-HOME', project_name: 'Pune Community Kitchen', purpose: 'Provide meals to families in Pune.',
	status: 'Active', starts_on: '2026-10-01', ends_on: '2026-12-31',
	can_submit_expense: true, can_request_advance: true, can_place_purchase_order: true,
};

async function mockHome(page: any, persona: string, projects = [project]) {
	await page.route('**/api/method/**', async (route: any) => {
		const name = new URL(route.request().url()).pathname.split('.').pop();
		let message: any = {};
		if (name === 'get_home_payload') message = {
			allowed: true, persona, full_name: 'Rahul Deshmukh', employee: 'EMP-HOME',
			flags: { show_member_projects: true }, member_projects: projects, nav: {}, actions: {},
			waiting: [], resume: [], waiting_count: 0,
		};
		if (name === 'get_purchase_workspace') message = {
			today: '2026-10-21', currency: 'INR', orders: [], projects: [{ value: 'PROJ-HOME', label: 'Pune Community Kitchen' }, { value: 'PROJ-OTHER', label: 'Another project' }],
			suppliers: [], items: [], warehouses: [], tax_templates: [], payment_accounts: [], expense_accounts: [], modes: [],
			capabilities: { create: true, accounts: false, manage_suppliers: false },
		};
		await route.fulfill({ json: { message } });
	});
}

for (const persona of ['employee', 'manager', 'projects manager', 'accounts manager', 'HR manager', 'director']) {
	test(`${persona} sees active projects first, opens details through the title, and places a project-linked order`, async ({ page }) => {
		await mockHome(page, persona);
		await page.goto('/volunteering/home');
		const section = page.locator('main section').first();
		await expect(section.getByRole('heading', { level: 1, name: 'Your active projects' })).toBeVisible();
		const card = section.locator('article').first();
		await expect(card.getByRole('heading', { name: project.project_name }).getByRole('link')).toHaveAttribute('href', /projects\?project=PROJ-HOME$/);
		await expect(card.getByRole('link', { name: 'View project', exact: true })).toHaveCount(0);
		for (const name of ['Submit an expense', 'Request an advance', 'Prepare an invoice', 'Place purchase order']) await expect(card.getByRole('link', { name, exact: true })).toBeVisible();
		await card.getByRole('link', { name: 'Place purchase order', exact: true }).click();
		await expect(page).toHaveURL(/vendor-purchases\?new=1&project=PROJ-HOME$/);
		await expect(page.getByRole('combobox', { name: 'Project *', exact: true })).toHaveValue(project.project_name);
	});
}

test('project tiles and the purchase action fit mobile without hiding other actions', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await mockHome(page, 'accounts manager');
	await page.goto('/volunteering/home');
	await expect(page.getByRole('link', { name: 'Place purchase order', exact: true })).toBeVisible();
	expect(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
	await page.screenshot({ path: 'output/qa/home-all-roles-projects-mobile.png', fullPage: true });
});

test('board-level employees can view their project title while existing purchase restrictions remain', async ({ page }) => {
	await mockHome(page, 'admin', [{ ...project, can_place_purchase_order: false }]);
	await page.goto('/volunteering/home');
	await expect(page.getByRole('heading', { name: project.project_name }).getByRole('link')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Place purchase order', exact: true })).toBeDisabled();
	await expect(page.getByRole('link', { name: 'Place purchase order', exact: true })).toHaveCount(0);
});

test('a person with no active member projects still gets the section and all-projects link', async ({ page }) => {
	await mockHome(page, 'accounts manager', []);
	await page.goto('/volunteering/home');
	await expect(page.getByRole('heading', { name: 'Your active projects', exact: true })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Open all projects', exact: true })).toHaveAttribute('href', /projects\?view=approved$/);
	await expect(page.getByText('No active projects list you as a member right now.', { exact: false })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Place purchase order', exact: true })).toHaveCount(0);
});

test('a forged or no-longer-eligible project URL is not preselected in a new purchase', async ({ page }) => {
	await mockHome(page, 'employee');
	await page.goto('/volunteering/vendor-purchases?new=1&project=PROJ-NOT-A-MEMBER');
	await expect(page.getByRole('combobox', { name: 'Project *', exact: true })).toHaveValue('');
});
