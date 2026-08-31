import { expect, test } from '@playwright/test';
import {
	addDays,
	cleanupDay,
	e2eCall,
	getCast,
	todayLocal,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { withPersona } from '../../helpers/persona-context';
import { personaStorage } from '../../helpers/personas';
import { getE2eProject } from '../../helpers/ui-fixtures';
import { DailyWorkLogFormPage } from '../../pages/desk/daily-work-log.page';
import { DeskForm } from '../../helpers/desk';

test.describe('HR Manager Notes & Dashboards @hr @ui', () => {
	test.describe('as manager', () => {
		test.use({ storageState: personaStorage('manager') });

		test('HR-MGR-001 @regression: Manager creates Appreciation note for report', async ({
			request,
		}) => {
			const cast = await getCast(request, 'manager');
			const emp = cast.employee.employee!;

			const created = await e2eCall<{ name: string }>(
				request,
				'seed_manager_note',
				{
					employee: emp,
					note_type: 'Appreciation',
					content: 'Excellent ownership shown during the E2E test sprint.',
				},
				'manager',
			);
			expect(created.name).toBeTruthy();

			const noteType = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Manager Note', name: created.name, field: 'note_type' },
				'admin',
			);
			expect(noteType).toBe('Appreciation');
		});

		test('HR-MGR-003 @regression: Manager note types Coaching and Warning', async ({
			request,
		}) => {
			const cast = await getCast(request, 'manager');
			const emp = cast.employee.employee!;

			const coaching = await e2eCall<{ name: string }>(
				request,
				'seed_manager_note',
				{
					employee: emp,
					note_type: 'Coaching',
					content: 'Coaching note for improving daily log discipline in E2E.',
				},
				'manager',
			);
			const warning = await e2eCall<{ name: string }>(
				request,
				'seed_manager_note',
				{
					employee: emp,
					note_type: 'Warning',
					content: 'Warning note recorded for policy reminder during E2E test.',
				},
				'manager',
			);

			expect(
				await e2eCall<string>(
					request,
					'get_doc_field',
					{ doctype: 'Manager Note', name: coaching.name, field: 'note_type' },
					'admin',
				),
			).toBe('Coaching');
			expect(
				await e2eCall<string>(
					request,
					'get_doc_field',
					{ doctype: 'Manager Note', name: warning.name, field: 'note_type' },
					'admin',
				),
			).toBe('Warning');
		});

		test('HR-MGR-005 @regression: Manager sees team work logs and marks reviewed', async ({
			request,
			browser,
		}) => {
			const cast = await getCast(request, 'manager');
			const emp = cast.employee.employee!;
			const date = workingDayFromToday(-1);
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			let logName = '';
			await withPersona(browser, 'employee', async (empPage) => {
				const dwl = new DailyWorkLogFormPage(empPage);
				await dwl.openNew();
				await dwl.setDate(date);
				await dwl.addItem({ project, hours: 6 });
				logName = await dwl.saveAndSubmit();
			});

			await e2eCall(
				request,
				'seed_mark_dwl_reviewed',
				{ name: logName, manager_remarks: 'Reviewed in E2E' },
				'manager',
			);

			const status = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Daily Work Log', name: logName, field: 'status' },
				'admin',
			);
			expect(status).toBe('Reviewed');
		});
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-MGR-002 @regression @critical: Employee cannot see manager notes', async ({
			page,
			request,
			browser,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;

			await e2eCall(
				request,
				'seed_manager_note',
				{
					employee: emp,
					note_type: 'Appreciation',
					content: 'Private manager note that employee must not see in E2E.',
				},
				'manager',
			);

			const desk = new DeskForm(page);
			await desk.gotoList('Manager Note');
			await expect(page.locator('.frappe-list').first()).toBeVisible();
			const rows = page.locator('.list-row-container .list-row');
			await expect(rows).toHaveCount(0);
		});
	});

	test.describe('as hr', () => {
		test.use({ storageState: personaStorage('hr') });

		test('HR-MGR-004 @regression: HR Accountability page loads for HR', async ({ page }) => {
			await page.goto('/desk/hr-accountability', { waitUntil: 'domcontentloaded' });
			await expect(page.locator('body')).toBeVisible();
			await expect(
				page.locator('.layout-main, .page-container, #body, .desk-sidebar').first(),
			).toBeVisible({ timeout: 30000 });
		});
	});
});
