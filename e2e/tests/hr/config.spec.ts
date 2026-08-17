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
import { getList } from '../../helpers/frappe';

test.describe('HR Configuration & Settings @hr', () => {
	test('HR-CFG-001 @regression @critical: Setting Reports To syncs Leave Approver', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const director = cast.director.employee!;
		const manager = cast.manager.employee!;

		await e2eCall(
			request,
			'set_employee_reports_to',
			{ employee: emp, reports_to: director },
			'admin',
		);
		const approver = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: emp, field: 'leave_approver' },
			'admin',
		);
		expect(approver).toBe(cast.director.email);

		await e2eCall(
			request,
			'set_employee_reports_to',
			{ employee: emp, reports_to: manager },
			'admin',
		);
		const restored = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: emp, field: 'leave_approver' },
			'admin',
		);
		expect(restored).toBe(cast.manager.email);
	});

	test('HR-CFG-002 @regression @critical: Wrong Reports To routes approvals incorrectly', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const director = cast.director.employee!;
		const manager = cast.manager.employee!;
		const date = workingDayFromToday(6);
		await cleanupDay(request, emp, date, 'admin');

		try {
			await e2eCall(
				request,
				'set_employee_reports_to',
				{ employee: emp, reports_to: director },
				'admin',
			);

			const wfh = await e2eCall<{ name: string }>(
				request,
				'create_wfh_request',
				{ employee: emp, date, submit: 0 },
				'employee',
			);

			let managerBlocked = false;
			try {
				await e2eCall(request, 'approve_wfh', { name: wfh.name }, 'manager');
			} catch {
				managerBlocked = true;
			}
			expect(managerBlocked).toBe(true);

			await e2eCall(request, 'approve_wfh', { name: wfh.name }, 'director');
		} finally {
			await e2eCall(
				request,
				'set_employee_reports_to',
				{ employee: emp, reports_to: manager },
				'admin',
			);
		}
	});

	test('HR-CFG-003 @regression: Designation set on Employee', async ({ request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;

		await e2eCall(
			request,
			'set_employee_field',
			{ employee: emp, field: 'designation', value: 'Manager' },
			'hr',
		);
		const designation = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: emp, field: 'designation' },
			'admin',
		);
		expect(designation).toBe('Manager');

		await e2eCall(
			request,
			'set_employee_field',
			{ employee: emp, field: 'designation', value: 'Program Officer' },
			'hr',
		);
	});

	test('HR-CFG-004 @regression: Department Head and Employee Department', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const fixtures = await e2eCall<{ department: string }>(request, 'get_fixtures', {}, 'admin');

		await e2eCall(
			request,
			'set_employee_field',
			{ employee: emp, field: 'department', value: fixtures.department },
			'hr',
		);
		const department = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: emp, field: 'department' },
			'admin',
		);
		expect(department).toBe(fixtures.department);
	});

	test('HR-CFG-005 @regression @critical: Unpaid employment type exclusions', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const unpaid = cast.unpaid.employee!;
		const employmentType = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: unpaid, field: 'employment_type' },
			'admin',
		);
		expect(employmentType).toMatch(/unpaid/i);

		const assignments = await getList<{ name: string }>(
			request,
			'Leave Policy Assignment',
			{ filters: { employee: unpaid }, limit: 1 },
		);
		expect(assignments.length).toBe(0);

		const digest = await e2eCall<{ html?: string }>(
			request,
			'preview_work_log_digest',
			{},
			'admin',
		);
		const unpaidName = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: unpaid, field: 'employee_name' },
			'admin',
		);
		expect(digest.html).toBeTruthy();
		expect(digest.html).not.toContain(unpaidName);
	});

	test('HR-CFG-006 @regression @critical: Paid employee gets standard leave policy', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const assignments = await getList<{ name: string; leave_policy: string }>(
			request,
			'Leave Policy Assignment',
			{ filters: { employee: emp, docstatus: 1 }, fields: ['name', 'leave_policy'], limit: 5 },
		);
		expect(assignments.length).toBeGreaterThan(0);
		expect(assignments[0].leave_policy).toBeTruthy();
	});

	test('HR-CFG-007 @regression: Change Present hours setting affects attendance', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = addDays(todayLocal(), -1);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(
			request,
			'set_single_setting',
			{ doctype: 'Daily Work Log Settings', field: 'present_hours_threshold', value: 7 },
			'admin',
		);

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
		expect(att?.status).toBe('Half Day');

		await e2eCall(
			request,
			'set_single_setting',
			{ doctype: 'Daily Work Log Settings', field: 'present_hours_threshold', value: 6 },
			'admin',
		);
	});

	test('HR-CFG-008 @regression: Change backdate limit setting', async ({ request }) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;

		try {
			await e2eCall(
				request,
				'set_single_setting',
				{ doctype: 'Daily Work Log Settings', field: 'backdate_limit_days', value: 1 },
				'admin',
			);

			const blocked = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_dwl',
				{ employee: emp, date: addDays(todayLocal(), -2), hours: 6 },
				'employee',
			);
			expect(blocked.ok).toBe(false);
			expectErrorContains(blocked.error || '', 'backdat');

			const yesterday = addDays(todayLocal(), -1);
			await cleanupDay(request, emp, yesterday, 'admin');
			const allowed = await e2eCall<{ ok: boolean }>(
				request,
				'try_create_dwl',
				{ employee: emp, date: yesterday, hours: 6 },
				'employee',
			);
			expect(allowed.ok).toBe(true);
		} finally {
			await e2eCall(
				request,
				'set_single_setting',
				{ doctype: 'Daily Work Log Settings', field: 'backdate_limit_days', value: 14 },
				'admin',
			);
		}
	});

	test('HR-CFG-009 @regression: Work log summary email preview', async ({ request }) => {
		const digest = await e2eCall<{
			html?: string;
			recipients?: string[];
			frequency?: string;
		}>(request, 'preview_work_log_digest', {}, 'admin');
		expect(digest.html).toBeTruthy();
		expect(digest.frequency).toBeTruthy();
	});

	test('HR-CFG-010 @regression: Leave Policy Settings page loads', async ({ page }) => {
		await page.goto('/desk/leave-policy-settings/Leave%20Policy%20Settings', {
			waitUntil: 'domcontentloaded',
		});
		await expect(page.locator('body')).toBeVisible();
	});

	test('HR-CFG-011 @regression @critical: Noon job finalizes yesterday attendance', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, emp, date, 'admin');

		const summary = await e2eCall<{ skipped?: boolean; processed?: number }>(
			request,
			'trigger_attendance_job',
			{ attendance_date: date },
			'admin',
		);
		expect(summary.skipped).not.toBe(true);
		expect((summary.processed || 0) > 0).toBe(true);

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Absent');
	});
});
