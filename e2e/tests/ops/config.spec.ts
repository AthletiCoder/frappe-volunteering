import { expect, test } from '@playwright/test';
import { e2eCall, getCast } from '../../helpers/e2e-api';
import { getList } from '../../helpers/frappe';
import { personaStorage, PERSONAS } from '../../helpers/personas';
import { DESK_WORKSPACE_RE, ROUTES } from '../../helpers/routes';

import { DailyWorkLogSettingsPage } from '../../pages/desk/dwl-settings.page';

test.describe('Ops email & digest config @ops @ui', () => {
	test.describe('as hr', () => {
		test.use({ storageState: personaStorage('hr') });

		test('HR-CFG-009 @regression: digest preview API returns html and recipients', async ({
			request,
		}) => {
			const preview = await e2eCall<{
				html: string;
				recipients: string[];
				frequency: string;
				label: string;
			}>(request, 'preview_work_log_digest');

			expect(preview.html.length).toBeGreaterThan(0);
			expect(preview.html.toLowerCase()).toMatch(/work log|summary|employee/);
			expect(Array.isArray(preview.recipients)).toBeTruthy();
			expect(preview.frequency).toBeTruthy();
			expect(preview.label).toBeTruthy();
		});

		test('digest preview excludes unpaid staff from body', async ({ request }) => {
			const cast = await getCast(request, 'admin');
			const unpaidEmp = cast.unpaid.employee!;
			const employeeName = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Employee', name: unpaidEmp, field: 'employee_name' },
				'admin',
			);

			const preview = await e2eCall<{ html: string }>(
				request,
				'preview_work_log_digest',
			);
			expect(preview.html).not.toContain(employeeName);
		});
	});

	test('Email Queue recent rows are readable @regression', async ({ request }) => {
		const rows = await getList(request, 'Email Queue', {
			fields: ['name', 'status', 'message_id', 'creation'],
			limit: 10,
			orderBy: 'creation desc',
		});
		expect(Array.isArray(rows)).toBeTruthy();
		for (const row of rows) {
			expect(row.name).toBeTruthy();
			expect(row.status).toBeTruthy();
		}
	});

	test('Daily Work Log Settings Preview Summary in UI @smoke', async ({ page }) => {
		const settings = new DailyWorkLogSettingsPage(page);
		await settings.open();
		await settings.previewSummary();
		await expect(page.locator('.modal-dialog, .msgprint').first()).toBeVisible({
			timeout: 15000,
		});
	});

	test('Daily Work Log Settings form opens @smoke', async ({ page }) => {
		await page.goto('/desk/daily-work-log-settings/Daily%20Work%20Log%20Settings', {
			waitUntil: 'domcontentloaded',
		});
		await expect(page.locator('body')).toBeVisible();
		await expect(
			page.locator('.layout-main, .page-container, #body, .desk-sidebar').first(),
		).toBeVisible({ timeout: 30000 });
	});

	test('Email Queue desk list opens @smoke', async ({ page }) => {
		await page.goto(ROUTES.emailQueue, { waitUntil: 'domcontentloaded' });
		await expect(page).toHaveURL(DESK_WORKSPACE_RE.emailQueue);
		await expect(
			page.locator('.layout-main, .page-container, #body, .desk-sidebar').first(),
		).toBeVisible({ timeout: 30000 });
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('employee cannot preview work log digest', async ({ request }) => {
			const response = await request.post(
				'/api/method/volunteering.volunteering.e2e_api.preview_work_log_digest',
				{
					data: {},
					headers: { 'Content-Type': 'application/json' },
				},
			);
			expect(response.ok()).toBeFalsy();
			const body = await response.text();
			expect(body.toLowerCase()).toMatch(/permission|not permitted|403/);
		});
	});
});
