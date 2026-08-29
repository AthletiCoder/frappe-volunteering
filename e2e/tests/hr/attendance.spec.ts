import { expect, test } from '@playwright/test';
import {
	cleanupDay,
	e2eCall,
	getCast,
	lastWednesday,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { expectFormError } from '../../helpers/dialogs';
import { withPersona } from '../../helpers/persona-context';
import { personaStorage } from '../../helpers/personas';
import { getE2eProject } from '../../helpers/ui-fixtures';
import { AttendanceRegularizationFormPage } from '../../pages/desk/attendance-regularization.page';
import { DailyWorkLogFormPage } from '../../pages/desk/daily-work-log.page';
import { LeaveApplicationFormPage } from '../../pages/desk/leave-application.page';
import { DeskForm } from '../../helpers/desk';

test.describe('HR Attendance @hr @ui', () => {
	test('HR-ATT-001 @regression @critical: No log after grace marks Absent', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Absent');
	});

	test('HR-ATT-002 @regression @critical: Late work log corrects Absent to Present', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-1);
		const project = await getE2eProject(request);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

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
		expect(att?.status).toBe('Present');
	});

	test('HR-ATT-003 @regression @critical: Holiday takes priority over logged hours', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = lastWednesday();
		const project = await getE2eProject(request);
		await cleanupDay(request, emp, date, 'admin');

		await withPersona(browser, 'employee', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 6 });
			await dwl.saveAndSubmit();
		});

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Holiday');
	});

	test('HR-ATT-004 @regression @critical: Approved leave takes priority over work log', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		const project = await getE2eProject(request);
		await cleanupDay(request, emp, date, 'admin');

		let leaveName = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: date, toDate: date, category: 'Emergency' });
			leaveName = await leave.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			await leave.setStatus('Approved');
		});

		await withPersona(browser, 'employee', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.addItem({ project, hours: 8 });
			await dwl.saveAndSubmit();
		});

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('On Leave');
	});

	test('HR-ATT-005 @regression @critical: Regularization locks status to Present', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		let regName = '';
		await withPersona(browser, 'employee', async (page) => {
			const reg = new AttendanceRegularizationFormPage(page);
			await reg.openNew();
			await reg.fillRequest({
				date,
				requestedStatus: 'Present',
				reason: 'Forgot to log work; hours were actually completed for E2E test.',
			});
			regName = await reg.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const reg = new AttendanceRegularizationFormPage(page);
			await reg.open(regName);
			await reg.approve();
		});

		const att = await e2eCall<{ status: string; name: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Present');

		const regularized = await e2eCall<number>(
			request,
			'get_doc_field',
			{
				doctype: 'Attendance',
				name: att!.name,
				field: 'custom_regularized',
			},
			'admin',
		);
		expect(regularized).toBe(1);
	});

	test('HR-ATT-006 @regression @critical: Only one open regularization per day', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-3);
		await cleanupDay(request, emp, date, 'admin');

		await withPersona(browser, 'employee', async (page) => {
			const reg = new AttendanceRegularizationFormPage(page);
			await reg.openNew();
			await reg.fillRequest({
				date,
				requestedStatus: 'Present',
				reason: 'First open regularization request for duplicate-day E2E test.',
			});
			await reg.saveAndSubmit();
		});

		await withPersona(browser, 'employee', async (page) => {
			const reg = new AttendanceRegularizationFormPage(page);
			await reg.openNew();
			await reg.fillRequest({
				date,
				requestedStatus: 'Half Day',
				reason: 'Second regularization should be blocked on the same date.',
			});
			await reg.save();
			await expectFormError(page, /already exists/i);
		});
	});

	test('HR-ATT-007 @regression: Manager rejects regularization', async ({ browser, request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-3);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		let regName = '';
		await withPersona(browser, 'employee', async (page) => {
			const reg = new AttendanceRegularizationFormPage(page);
			await reg.openNew();
			await reg.fillRequest({
				date,
				requestedStatus: 'Present',
				reason: 'Requesting Present after missed log; manager will reject in E2E.',
			});
			regName = await reg.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const reg = new AttendanceRegularizationFormPage(page);
			await reg.open(regName);
			await reg.reject();
		});

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Absent');
	});

	test('HR-ATT-008 @regression @critical: Unpaid employee excluded from attendance job', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const unpaid = cast.unpaid.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, unpaid, date, 'admin');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		const att = await e2eCall<null>(
			request,
			'get_attendance_status',
			{ employee: unpaid, date },
			'admin',
		);
		expect(att).toBeFalsy();
	});

	test('HR-ATT-009 @regression: Regularization beats approved leave', async ({ browser, request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-4);
		await cleanupDay(request, emp, date, 'admin');

		let leaveName = '';
		await withPersona(browser, 'hr', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.setEmployee(emp);
			await leave.fillLeave({ fromDate: date, toDate: date, category: 'Emergency' });
			leaveName = await leave.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			await leave.setStatus('Approved');
		});

		let regName = '';
		await withPersona(browser, 'employee', async (page) => {
			const reg = new AttendanceRegularizationFormPage(page);
			await reg.openNew();
			await reg.fillRequest({
				date,
				requestedStatus: 'Present',
				reason: 'Approved leave exists but regularization should lock Present status.',
			});
			regName = await reg.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const reg = new AttendanceRegularizationFormPage(page);
			await reg.open(regName);
			await reg.approve();
		});

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Present');
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-ATT-010 @regression: View own attendance list', async ({ page }) => {
			const desk = new DeskForm(page);
			await desk.gotoList('Attendance');
			await expect(page.locator('.list-row, .frappe-list')).toBeVisible();
			await expect(page.locator('.list-row-head, .list-headers')).toBeVisible();
			await expect(page.locator('.filter-section, .standard-filter-section, .filter-selector')).toBeVisible();
		});
	});
});
