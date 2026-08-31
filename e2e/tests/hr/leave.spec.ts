import { expect, test } from '@playwright/test';
import {
	addDays,
	cleanupDay,
	cleanupLeaveSpan,
	e2eCall,
	getCast,
	todayLocal,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { withPersona } from '../../helpers/persona-context';
import { personaStorage } from '../../helpers/personas';
import { LeaveApplicationFormPage } from '../../pages/desk/leave-application.page';

const LWP = 'Leave Without Pay';

async function cleanupRange(
	request: Parameters<typeof cleanupDay>[0],
	employee: string,
	from: string,
	to: string,
): Promise<void> {
	let date = from;
	while (date <= to) {
		await cleanupDay(request, employee, date, 'admin');
		date = addDays(date, 1);
	}
}

test.describe('HR Leave Application @hr @ui', () => {
	test('HR-LV-001 @regression @critical: Normal Privilege Leave with sufficient notice', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(5);
		const to = addDays(from, 2);
		for (const d of [from, addDays(from, 1), to]) {
			await cleanupDay(request, emp, d, 'admin');
		}

		let leaveName = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: from, toDate: to, category: 'Normal' });
			leaveName = await leave.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			await leave.setStatus('Approved');
		});

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: from }, 'admin');
		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date: from },
			'admin',
		);
		expect(att?.status).toBe('On Leave');
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-LV-002 @regression @critical: Normal leave with past start date blocked', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = workingDayFromToday(-1);
			await cleanupDay(request, emp, date, 'admin');

			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: date, toDate: date, category: 'Normal' });
			await leave.save({ expectError: /backdat/i });
		});

		test('HR-LV-003 @regression @critical: Normal leave insufficient notice blocked', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const from = workingDayFromToday(1);
			const to = addDays(from, 2);
			await cleanupRange(request, emp, from, to);

			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: from, toDate: to, category: 'Normal' });
			await leave.save({ expectError: /notice/i });
		});
	});

	test('HR-LV-004 @regression: Leave Without Pay application', async ({ browser, request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(10);
		const to = from;
		await cleanupDay(request, emp, from, 'admin');

		let leaveName = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({
				fromDate: from,
				toDate: to,
				category: 'Normal',
				leaveType: LWP,
			});
			leaveName = await leave.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			await leave.setStatus('Approved');
		});

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: from }, 'admin');
		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date: from },
			'admin',
		);
		expect(att?.status).toBe('On Leave');
	});

	test('HR-LV-005 @regression @critical: Emergency leave within 3 consecutive days', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(1);
		const to = addDays(from, 1);
		await cleanupRange(request, emp, from, to);

		let leaveName = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: from, toDate: to, category: 'Emergency' });
			leaveName = await leave.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			await leave.setStatus('Approved');
		});

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: from }, 'admin');
		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date: from },
			'admin',
		);
		expect(att?.status).toBe('On Leave');
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-LV-006 @regression @critical: Emergency leave more than 3 consecutive days blocked', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const from = todayLocal();
			const to = addDays(from, 3);
			await cleanupRange(request, emp, from, to);

			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: from, toDate: to, category: 'Emergency' });
			await leave.save({ expectError: /3/ });
		});
	});

	test('HR-LV-007 @regression @critical: Emergency leave within 48 hours after return', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(-1);
		const to = from;
		await cleanupDay(request, emp, from, 'admin');

		let leaveName = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: from, toDate: to, category: 'Emergency' });
			leaveName = await leave.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			await leave.setStatus('Approved');
		});
		expect(leaveName).toBeTruthy();
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-LV-008 @regression @critical: Emergency leave after 48 hours without HR blocked', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const from = workingDayFromToday(-10);
			const to = addDays(from, 2);
			await cleanupRange(request, emp, from, to);

			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: from, toDate: to, category: 'Emergency' });
			await leave.save({ expectError: /48/ });
		});
	});

	test('HR-LV-009 @regression: HR can add late emergency leave', async ({ browser, request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(-10);
		const to = addDays(from, 2);
		await cleanupRange(request, emp, from, to);

		let leaveName = '';
		const created = await e2eCall<{ name: string }>(
			request,
			'seed_leave_application',
			{
				employee: emp,
				category: 'Emergency',
				from_date: from,
				to_date: to,
				leave_approver: cast.manager.email,
			},
			'admin',
		);
		leaveName = created.name;

		await e2eCall(
			request,
			'seed_set_leave_status',
			{ name: leaveName, status: 'Approved' },
			'hr',
		);

		const status = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Leave Application', name: leaveName, field: 'status' },
			'admin',
		);
		expect(status).toBe('Approved');
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-LV-010 @regression @critical: Long leave requires Board Chairperson approver', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'admin');
			const emp = cast.employee.employee!;
			const from = addDays(todayLocal(), 30);
			const to = addDays(todayLocal(), 50);
			await cleanupLeaveSpan(request, emp, from, to);

			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({
				fromDate: from,
				toDate: to,
				category: 'Normal',
				leaveApprover: cast.manager.email,
			});
			await leave.save({ expectError: /grade/i });
		});
	});

	test('HR-LV-011 @regression @critical: Long leave approved by Board Chairperson', async ({
		browser,
		request,
	}) => {
		test.setTimeout(90_000);
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = addDays(todayLocal(), 30);
		const to = addDays(todayLocal(), 50);
		await cleanupLeaveSpan(request, emp, from, to);

		let leaveName = '';
		const created = await e2eCall<{ name: string }>(
			request,
			'seed_leave_application',
			{
				employee: emp,
				category: 'Normal',
				from_date: from,
				to_date: to,
				leave_approver: cast.chair.email,
			},
			'admin',
		);
		leaveName = created.name;

		await withPersona(browser, 'chair', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			await leave.setStatus('Approved');
		});

		const status = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Leave Application', name: leaveName, field: 'status' },
			'admin',
		);
		expect(status).toBe('Approved');
	});

	test('HR-LV-012 @regression @critical: Employee cannot approve own leave', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(8);
		const to = from;
		await cleanupDay(request, emp, from, 'admin');

		let leaveName = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: from, toDate: to, category: 'Normal' });
			leaveName = await leave.saveAndSubmit();
		});

		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			expect(await leave.workflowActionVisible('Approve')).toBe(false);
			expect(await leave.workflowActionVisible('Reject')).toBe(false);
		});
	});

	test('HR-LV-013 @regression: Leave Approver auto-filled from Reports To', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const approver = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: emp, field: 'leave_approver' },
			'admin',
		);
		expect(approver).toBe(cast.manager.email);

		const date = workingDayFromToday(16);
		await cleanupDay(request, emp, date, 'admin');

		let leaveName = '';
		let leaveApprover = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: date, toDate: date, category: 'Normal' });
			leaveApprover = await leave.readLinkValue('leave_approver');
			leaveName = await leave.saveDraft();
		});
		expect(leaveApprover).toBe(cast.manager.email);
		expect(leaveName).toBeTruthy();
	});

	test('HR-LV-014 @regression: Reject leave does not mark On Leave', async ({ browser, request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(12);
		await cleanupDay(request, emp, date, 'admin');

		let leaveName = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: date, toDate: date, category: 'Normal' });
			leaveName = await leave.saveAndSubmit();
		});

		await withPersona(browser, 'manager', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.open(leaveName);
			await leave.setStatus('Rejected');
		});

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');
		const att = await e2eCall<{ status: string } | null>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).not.toBe('On Leave');
	});
});
