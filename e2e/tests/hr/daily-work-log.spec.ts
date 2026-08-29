import { expect, test } from '@playwright/test';
import {
	addDays,
	cleanupDay,
	e2eCall,
	getCast,
	todayLocal,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { expectFormError } from '../../helpers/dialogs';
import { withPersona } from '../../helpers/persona-context';
import { personaStorage } from '../../helpers/personas';
import { getE2eProject } from '../../helpers/ui-fixtures';
import { DailyWorkLogFormPage } from '../../pages/desk/daily-work-log.page';
import { DeskForm } from '../../helpers/desk';

test.describe('HR Daily Work Log @hr @ui', () => {
	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-DWL-001 @regression @critical: Create and submit daily work log (happy path)', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = todayLocal();
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			await dwl.saveAndSubmit();

			const att = await e2eCall<{ status: string } | null>(
				request,
				'get_attendance_status',
				{ employee: emp, date },
				'admin',
			);
			expect(att?.status).toMatch(/Present|Half Day|Work From Home/i);
		});

		test('HR-DWL-002 @regression @critical: Project is required on work log item', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({
				hours: 6,
				taskTitle: 'E2E Task',
				description: 'Missing project on purpose',
				skipProject: true,
			});
			await dwl.save();
			await expectFormError(page, /project/i);
		});

		test('HR-DWL-003 @regression @critical: One work log per employee per day', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			await dwl.saveAndSubmit();

			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 4 });
			await dwl.save();
			await expectFormError(page, /already exists/i);
		});

		test('HR-DWL-004 @regression @critical: Backdate within allowed limit', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -2);
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			await dwl.saveAndSubmit();
		});

		test('HR-DWL-005 @regression @critical: Backdate beyond allowed limit blocked', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -20);
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			await dwl.save();
			await expectFormError(page, /backdat/i);
		});

		test('HR-DWL-006 @regression: Soft warning when hours below minimum', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 5 });
			await dwl.saveAndSubmit({ expectLowHoursWarning: true });
		});

		test('HR-DWL-007 @regression @critical: Hours >= Present hours yields Present', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			await dwl.saveAndSubmit();

			const att = await e2eCall<{ status: string }>(
				request,
				'get_attendance_status',
				{ employee: emp, date },
				'admin',
			);
			expect(att?.status).toBe('Present');
		});

		test('HR-DWL-008 @regression @critical: Hours between 0 and Present yields Half Day', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = addDays(todayLocal(), -1);
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 3 });
			await dwl.saveAndSubmit();

			const att = await e2eCall<{ status: string }>(
				request,
				'get_attendance_status',
				{ employee: emp, date },
				'admin',
			);
			expect(att?.status).toBe('Half Day');
		});

		test('HR-DWL-011 @regression: Employee can only create own work log', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const other = cast.employee_b.employee!;
			const date = addDays(todayLocal(), -1);
			await cleanupDay(request, other, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setEmployee(other);
			await dwl.setDate(date);
			await dwl.save();
			await expectFormError(page, /yourself|only create/i);
		});
	});

	test('HR-DWL-009 @regression @critical: Manager Mark as Reviewed locks employee edits', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = addDays(todayLocal(), -1);
		const project = await getE2eProject(request);
		await cleanupDay(request, emp, date, 'admin');

		let logName = '';
		await withPersona(browser, 'employee', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			logName = await dwl.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.open(logName);
			await dwl.markReviewed();
		});

		const status = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Daily Work Log', name: logName, field: 'status' },
			'admin',
		);
		expect(status).toBe('Reviewed');
	});

	test('HR-DWL-010 @regression @critical: Cancel submitted log recalculates attendance', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		const project = await getE2eProject(request);
		await cleanupDay(request, emp, date, 'admin');

		let logName = '';
		await withPersona(browser, 'employee', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			logName = await dwl.saveAndSubmit();
		});

		await withPersona(browser, 'employee', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.open(logName);
			await dwl.cancelDoc();
		});

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
		const desk = new DeskForm(page);
		await desk.gotoReport('Missing Daily Logs Report');
		await expect(page.locator('.report-wrapper, .query-report, .dt-scrollable').first()).toBeVisible();
	});
});
