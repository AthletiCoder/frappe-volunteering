import { expect, test } from '@playwright/test';
import {
	addDays,
	cleanupDay,
	e2eCall,
	getCast,
	todayLocal,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { expectFormError, expectMsgprint } from '../../helpers/dialogs';
import { withPersona } from '../../helpers/persona-context';
import { personaStorage } from '../../helpers/personas';
import { getE2eProject } from '../../helpers/ui-fixtures';
import { getList } from '../../helpers/frappe';
import { AttendanceRequestFormPage } from '../../pages/desk/attendance-request.page';
import { DailyWorkLogFormPage } from '../../pages/desk/daily-work-log.page';
import { DailyWorkLogSettingsPage } from '../../pages/desk/dwl-settings.page';
import { DeskForm } from '../../helpers/desk';
import { EmployeeFormPage } from '../../pages/desk/employee.page';

test.describe('HR Configuration & Settings @hr @ui', () => {
	test('HR-CFG-001 @regression @critical: Setting Reports To syncs Leave Approver', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const director = cast.director.employee!;
		const manager = cast.manager.employee!;

		await withPersona(browser, 'admin', async (page) => {
			const employee = new EmployeeFormPage(page);
			await employee.open(emp);
			await employee.setReportsTo(director);
			const approver = await employee.readField('leave_approver');
			expect(approver).toBe(cast.director.email);

			await employee.setReportsTo(manager);
			const restored = await employee.readField('leave_approver');
			expect(restored).toBe(cast.manager.email);
		});
	});

	test('HR-CFG-002 @regression @critical: Wrong Reports To routes approvals incorrectly', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const director = cast.director.employee!;
		const manager = cast.manager.employee!;
		const date = workingDayFromToday(6);
		await cleanupDay(request, emp, date, 'admin');

		try {
			await withPersona(browser, 'admin', async (page) => {
				const employee = new EmployeeFormPage(page);
				await employee.open(emp);
				await employee.setReportsTo(director);
			});

			let wfhName = '';
			await withPersona(browser, 'employee', async (page) => {
				const wfh = new AttendanceRequestFormPage(page);
				await wfh.openNew();
				await wfh.fillWfhRequest(date);
				wfhName = await wfh.saveDraft();
			});

			await withPersona(browser, 'manager', async (page) => {
				const wfh = new AttendanceRequestFormPage(page);
				await wfh.open(wfhName);
				await wfh.submit();
				await expectFormError(page, /cannot approve|permission|not permitted/i);
			});

			await withPersona(browser, 'director', async (page) => {
				const wfh = new AttendanceRequestFormPage(page);
				await wfh.open(wfhName);
				await wfh.submitRequest();
			});
		} finally {
			await e2eCall(
				request,
				'set_employee_reports_to',
				{ employee: emp, reports_to: manager },
				'admin',
			);
		}
	});

	test('HR-CFG-003 @regression: Designation set on Employee', async ({ browser, request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;

		await withPersona(browser, 'hr', async (page) => {
			const employee = new EmployeeFormPage(page);
			await employee.open(emp);
			await employee.setField('designation', 'Manager');
			const designation = await employee.readField('designation');
			expect(designation).toBe('Manager');
			await employee.setField('designation', 'Program Officer');
		});
	});

	test('HR-CFG-004 @regression: Department Head and Employee Department', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const fixtures = await e2eCall<{ department: string }>(request, 'get_fixtures', {}, 'admin');

		await withPersona(browser, 'hr', async (page) => {
			const employee = new EmployeeFormPage(page);
			await employee.open(emp);
			await employee.setField('department', fixtures.department);
			const department = await employee.readField('department');
			expect(department).toBe(fixtures.department);
		});
	});

	test('HR-CFG-005 @regression @critical: Unpaid employment type exclusions', async ({
		browser,
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

		const unpaidName = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: unpaid, field: 'employee_name' },
			'admin',
		);

		await withPersona(browser, 'admin', async (page) => {
			const settings = new DailyWorkLogSettingsPage(page);
			await settings.open();
			await settings.previewSummary();
			await expectMsgprint(page, /.+/);
		});

		const digest = await e2eCall<{ html?: string }>(
			request,
			'preview_work_log_digest',
			{},
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
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = addDays(todayLocal(), -1);
		const project = await getE2eProject(request);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(
			request,
			'set_single_setting',
			{ doctype: 'Daily Work Log Settings', field: 'present_hours_threshold', value: 7 },
			'admin',
		);

		await withPersona(browser, 'employee', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			await dwl.saveAndSubmit();
		});

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

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-CFG-008 @regression: Change backdate limit setting', async ({ page, request }) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const project = await getE2eProject(request);

			try {
				await e2eCall(
					request,
					'set_single_setting',
					{ doctype: 'Daily Work Log Settings', field: 'backdate_limit_days', value: 1 },
					'admin',
				);

				const dwl = new DailyWorkLogFormPage(page);
				await dwl.openNew();
				await dwl.setDate(addDays(todayLocal(), -2));
				await dwl.addItem({ project, hours: 6 });
				await dwl.save();
				await expectFormError(page, /backdat/i);

				const yesterday = addDays(todayLocal(), -1);
				await cleanupDay(request, emp, yesterday, 'admin');
				await dwl.openNew();
				await dwl.setDate(yesterday);
				await dwl.addItem({ project, hours: 6 });
				await dwl.saveAndSubmit();
			} finally {
				await e2eCall(
					request,
					'set_single_setting',
					{ doctype: 'Daily Work Log Settings', field: 'backdate_limit_days', value: 14 },
					'admin',
				);
			}
		});
	});

	test('HR-CFG-009 @regression: Work log summary email preview', async ({ browser }) => {
		await withPersona(browser, 'admin', async (page) => {
			const settings = new DailyWorkLogSettingsPage(page);
			await settings.open();
			await settings.previewSummary();
			await expectMsgprint(page, /.+/);
		});
	});

	test('HR-CFG-010 @regression: Leave Policy Settings page loads', async ({ page }) => {
		const desk = new DeskForm(page);
		await desk.gotoForm('Leave Policy Settings', 'Leave Policy Settings');
		await expect(page.locator('[data-fieldname="default_leave_type"]')).toBeVisible();
		await expect(page.locator('[data-fieldname="emergency_max_consecutive_days"]')).toBeVisible();
		await expect(page.locator('[data-fieldname="planned_leave_advance_days"]')).toBeVisible();
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
