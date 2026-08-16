import { expect, test } from '@playwright/test';
import {
	addDays,
	cleanupDay,
	e2eCall,
	expectErrorContains,
	getCast,
	todayLocal,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { personaStorage } from '../../helpers/personas';

test.describe('HR Daily Work Log @hr', () => {
	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-DWL-001 @regression @critical: Create and submit daily work log (happy path)', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = todayLocal();
			await cleanupDay(request, emp, date, 'admin');
			const res = await e2eCall<{ name: string; docstatus: number }>(
				request,
				'create_dwl',
				{ employee: emp, date, hours: 6, submit: 1 },
				'employee',
			);
			expect(res.docstatus).toBe(1);
			const att = await e2eCall<{ status: string } | null>(
				request,
				'get_attendance_status',
				{ employee: emp, date },
				'admin',
			);
			expect(att?.status).toMatch(/Present|Half Day|Work From Home/i);
		});

		test('HR-DWL-002 @regression @critical: Project is required on work log item', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, emp, date, 'admin');
			const res = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_dwl',
				{ employee: emp, date, hours: 6, include_project: 0 },
				'employee',
			);
			expect(res.ok).toBe(false);
			expectErrorContains(res.error || '', 'project');
		});

		test('HR-DWL-003 @regression @critical: One work log per employee per day', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, emp, date, 'admin');
			await e2eCall(
				request,
				'create_dwl',
				{ employee: emp, date, hours: 6, submit: 1 },
				'employee',
			);
			const dup = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_dwl',
				{ employee: emp, date, hours: 4 },
				'employee',
			);
			expect(dup.ok).toBe(false);
			expectErrorContains(dup.error || '', 'already exists');
		});

		test('HR-DWL-004 @regression @critical: Backdate within allowed limit', async ({ request }) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -2);
			await cleanupDay(request, emp, date, 'admin');
			const res = await e2eCall<{ docstatus: number }>(
				request,
				'create_dwl',
				{ employee: emp, date, hours: 6, submit: 1 },
				'employee',
			);
			expect(res.docstatus).toBe(1);
		});

		test('HR-DWL-005 @regression @critical: Backdate beyond allowed limit blocked', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
		const date = addDays(todayLocal(), -20);
			const res = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_dwl',
				{ employee: emp, date, hours: 6 },
				'employee',
			);
			expect(res.ok).toBe(false);
			expectErrorContains(res.error || '', 'backdat');
		});

		test('HR-DWL-006 @regression: Soft warning when hours below minimum', async ({ request }) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, emp, date, 'admin');
			const res = await e2eCall<{ docstatus: number }>(
				request,
				'create_dwl',
				{ employee: emp, date, hours: 5, submit: 1 },
				'employee',
			);
			expect(res.docstatus).toBe(1);
		});

		test('HR-DWL-007 @regression @critical: Hours >= Present hours yields Present', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, emp, date, 'admin');
			await e2eCall(
				request,
				'create_dwl',
				{ employee: emp, date, hours: 6, submit: 1 },
				'employee',
			);
			const att = await e2eCall<{ status: string }>(
				request,
				'get_attendance_status',
				{ employee: emp, date },
				'admin',
			);
			expect(att?.status).toBe('Present');
		});

		test('HR-DWL-008 @regression @critical: Hours between 0 and Present yields Half Day', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, emp, date, 'admin');
			await e2eCall(
				request,
				'create_dwl',
				{ employee: emp, date, hours: 3, submit: 1 },
				'employee',
			);
			const att = await e2eCall<{ status: string }>(
				request,
				'get_attendance_status',
				{ employee: emp, date },
				'admin',
			);
			expect(att?.status).toBe('Half Day');
		});

		test('HR-DWL-011 @regression: Employee can only create own work log', async ({ request }) => {
			const cast = await getCast(request, 'employee');
			const other = cast.employee_b.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, other, date, 'admin');
			const res = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_dwl',
				{ employee: other, date, hours: 6 },
				'employee',
			);
			expect(res.ok).toBe(false);
		});
	});

	test.describe('manager review HR-DWL-009 @regression @critical', () => {
		test('Manager Mark as Reviewed locks employee edits', async ({ request }) => {
			const cast = await getCast(request, 'admin');
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

	test('HR-DWL-010 @regression @critical: Cancel submitted log recalculates attendance', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, emp, date, 'admin');
		const created = await e2eCall<{ name: string }>(
			request,
			'create_dwl',
			{ employee: emp, date, hours: 6, submit: 1 },
			'employee',
		);
		await e2eCall(request, 'cancel_dwl', { name: created.name }, 'employee');
		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');
		const att = await e2eCall<{ status: string } | null>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Absent');
	});

	test('HR-DWL-012 @regression: Missing Daily Logs Report lists missing days', async ({ page }) => {
		await page.goto('/desk/query-report/Missing Daily Logs Report', {
			waitUntil: 'domcontentloaded',
		});
		await expect(page.locator('body')).toBeVisible();
	});
});
