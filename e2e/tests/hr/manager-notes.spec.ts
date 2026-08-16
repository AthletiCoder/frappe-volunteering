import { expect, test } from '@playwright/test';
import {
	addDays,
	cleanupDay,
	e2eCall,
	getCast,
	todayLocal,
} from '../../helpers/e2e-api';
import { callMethod } from '../../helpers/frappe';
import { personaStorage } from '../../helpers/personas';

test.describe('HR Manager Notes & Dashboards @hr', () => {
	test.describe('as manager', () => {
		test.use({ storageState: personaStorage('manager') });

		test('HR-MGR-001 @regression: Manager creates Appreciation note for report', async ({
			request,
		}) => {
			const cast = await getCast(request, 'manager');
			const emp = cast.employee.employee!;

			const name = await e2eCall<string>(
				request,
				'create_manager_note',
				{
					employee: emp,
					note_type: 'Appreciation',
					content: 'Excellent ownership shown during the E2E test sprint.',
				},
				'manager',
			);
			expect(name).toBeTruthy();

			const noteType = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Manager Note', name, field: 'note_type' },
				'admin',
			);
			expect(noteType).toBe('Appreciation');
		});

		test('HR-MGR-003 @regression: Manager note types Coaching and Warning', async ({
			request,
		}) => {
			const cast = await getCast(request, 'manager');
			const emp = cast.employee.employee!;

			const coaching = await e2eCall<string>(
				request,
				'create_manager_note',
				{
					employee: emp,
					note_type: 'Coaching',
					content: 'Coaching note for improving daily log discipline in E2E.',
				},
				'manager',
			);
			const warning = await e2eCall<string>(
				request,
				'create_manager_note',
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
					{ doctype: 'Manager Note', name: coaching, field: 'note_type' },
					'admin',
				),
			).toBe('Coaching');
			expect(
				await e2eCall<string>(
					request,
					'get_doc_field',
					{ doctype: 'Manager Note', name: warning, field: 'note_type' },
					'admin',
				),
			).toBe('Warning');
		});

		test('HR-MGR-005 @regression: Manager sees team work logs and marks reviewed', async ({
			request,
		}) => {
			const cast = await getCast(request, 'manager');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, emp, date, 'admin');

			const created = await e2eCall<{ name: string }>(
				request,
				'create_dwl',
				{ employee: emp, date, hours: 6, submit: 1 },
				'employee',
			);
			await e2eCall(
				request,
				'mark_dwl_reviewed',
				{ name: created.name },
				'manager',
			);
			const status = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Daily Work Log', name: created.name, field: 'status' },
				'admin',
			);
			expect(status).toBe('Reviewed');
		});
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-MGR-002 @regression @critical: Employee cannot see manager notes', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;

			await e2eCall(
				request,
				'create_manager_note',
				{
					employee: emp,
					note_type: 'Appreciation',
					content: 'Private manager note that employee must not see in E2E.',
				},
				'manager',
			);

			const notes = await callMethod<{ name: string }[]>(
				request,
				'frappe.client.get_list',
				{
					doctype: 'Manager Note',
					filters: { employee: emp },
					fields: ['name'],
					limit_page_length: 10,
				},
				'employee',
			);
			expect(notes.length).toBe(0);
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
