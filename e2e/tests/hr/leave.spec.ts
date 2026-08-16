import { expect, test } from '@playwright/test';
import {
	addDays,
	cleanupDay,
	cleanupLeaveSpan,
	e2eCall,
	expectErrorContains,
	getCast,
	todayLocal,
	workingDayFromToday,
} from '../../helpers/e2e-api';

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

test.describe('HR Leave Application @hr', () => {
	test('HR-LV-001 @regression @critical: Normal Privilege Leave with sufficient notice', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(5);
		const to = addDays(from, 2);
		for (const d of [from, addDays(from, 1), to]) {
			await cleanupDay(request, emp, d, 'admin');
		}

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{ employee: emp, category: 'Normal', from_date: from, to_date: to, submit: 1 },
			'employee',
		);
		await e2eCall(
			request,
			'set_leave_status',
			{ name: leave.name, status: 'Approved' },
			'manager',
		);

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: from }, 'admin');
		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date: from },
			'admin',
		);
		expect(att?.status).toBe('On Leave');
	});

	test('HR-LV-002 @regression @critical: Normal leave with past start date blocked', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-1);
		await cleanupDay(request, emp, date, 'admin');
		const res = await e2eCall<{ ok: boolean; error?: string }>(
			request,
			'try_create_leave',
			{
				employee: emp,
				category: 'Normal',
				from_date: date,
				to_date: date,
			},
			'employee',
		);
		expect(res.ok).toBe(false);
		expectErrorContains(res.error || '', 'backdat');
	});

	test('HR-LV-003 @regression @critical: Normal leave insufficient notice blocked', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(1);
		const to = addDays(from, 2);
		await cleanupRange(request, emp, from, to);
		const res = await e2eCall<{ ok: boolean; error?: string }>(
			request,
			'try_create_leave',
			{ employee: emp, category: 'Normal', from_date: from, to_date: to },
			'employee',
		);
		expect(res.ok).toBe(false);
		expectErrorContains(res.error || '', 'notice');
	});

	test('HR-LV-004 @regression: Leave Without Pay application', async ({ request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(10);
		const to = from;
		await cleanupDay(request, emp, from, 'admin');

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{
				employee: emp,
				category: 'Normal',
				from_date: from,
				to_date: to,
				leave_type: LWP,
				submit: 1,
			},
			'employee',
		);
		await e2eCall(
			request,
			'set_leave_status',
			{ name: leave.name, status: 'Approved' },
			'manager',
		);

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
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(1);
		const to = addDays(from, 1);
		await cleanupRange(request, emp, from, to);

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{ employee: emp, category: 'Emergency', from_date: from, to_date: to, submit: 1 },
			'employee',
		);
		await e2eCall(
			request,
			'set_leave_status',
			{ name: leave.name, status: 'Approved' },
			'manager',
		);

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: from }, 'admin');
		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date: from },
			'admin',
		);
		expect(att?.status).toBe('On Leave');
	});

	test('HR-LV-006 @regression @critical: Emergency leave more than 3 consecutive days blocked', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const from = todayLocal();
		const to = addDays(from, 3);
		await cleanupRange(request, emp, from, to);
		const res = await e2eCall<{ ok: boolean; error?: string }>(
			request,
			'try_create_leave',
			{
				employee: emp,
				category: 'Emergency',
				from_date: from,
				to_date: to,
			},
			'employee',
		);
		expect(res.ok).toBe(false);
		expectErrorContains(res.error || '', '3');
	});

	test('HR-LV-007 @regression @critical: Emergency leave within 48 hours after return', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(-1);
		const to = from;
		await cleanupDay(request, emp, from, 'admin');

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{ employee: emp, category: 'Emergency', from_date: from, to_date: to, submit: 1 },
			'employee',
		);
		await e2eCall(
			request,
			'set_leave_status',
			{ name: leave.name, status: 'Approved' },
			'manager',
		);
		expect(leave.name).toBeTruthy();
	});

	test('HR-LV-008 @regression @critical: Emergency leave after 48 hours without HR blocked', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(-10);
		const to = addDays(from, 2);
		await cleanupRange(request, emp, from, to);
		const res = await e2eCall<{ ok: boolean; error?: string }>(
			request,
			'try_create_leave',
			{
				employee: emp,
				category: 'Emergency',
				from_date: from,
				to_date: to,
			},
			'employee',
		);
		expect(res.ok).toBe(false);
		expectErrorContains(res.error || '', '48');
	});

	test('HR-LV-009 @regression: HR can add late emergency leave', async ({ request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(-10);
		const to = addDays(from, 2);
		await cleanupRange(request, emp, from, to);

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{ employee: emp, category: 'Emergency', from_date: from, to_date: to, submit: 1 },
			'hr',
		);
		await e2eCall(
			request,
			'set_leave_status',
			{ name: leave.name, status: 'Approved' },
			'hr',
		);
		const status = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Leave Application', name: leave.name, field: 'status' },
			'admin',
		);
		expect(status).toBe('Approved');
	});

	test('HR-LV-010 @regression @critical: Long leave requires Board Chairperson approver', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = addDays(todayLocal(), 30);
		const to = addDays(todayLocal(), 50);
		await cleanupLeaveSpan(request, emp, from, to);
		const res = await e2eCall<{ ok: boolean; error?: string }>(
			request,
			'try_create_leave',
			{
				employee: emp,
				category: 'Normal',
				from_date: from,
				to_date: to,
				leave_approver: cast.manager.email,
			},
			'employee',
		);
		expect(res.ok).toBe(false);
		expectErrorContains(res.error || '', 'grade');
	});

	test('HR-LV-011 @regression @critical: Long leave approved by Board Chairperson', async ({
		request,
	}) => {
		test.setTimeout(90_000);
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = addDays(todayLocal(), 30);
		const to = addDays(todayLocal(), 50);
		await cleanupLeaveSpan(request, emp, from, to);

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{
				employee: emp,
				category: 'Normal',
				from_date: from,
				to_date: to,
				leave_approver: cast.chair.email,
				submit: 1,
			},
			'employee',
		);
		await e2eCall(
			request,
			'set_leave_status',
			{ name: leave.name, status: 'Approved' },
			'chair',
		);
		const status = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Leave Application', name: leave.name, field: 'status' },
			'admin',
		);
		expect(status).toBe('Approved');
	});

	test('HR-LV-012 @regression @critical: Employee cannot approve own leave', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const from = workingDayFromToday(8);
		const to = from;
		await cleanupDay(request, emp, from, 'admin');

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{ employee: emp, category: 'Normal', from_date: from, to_date: to, submit: 1 },
			'employee',
		);

		let blocked = false;
		try {
			await e2eCall(
				request,
				'set_leave_status',
				{ name: leave.name, status: 'Approved' },
				'employee',
			);
		} catch {
			blocked = true;
		}
		expect(blocked).toBe(true);
	});

	test('HR-LV-013 @regression: Leave Approver auto-filled from Reports To', async ({
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

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{
				employee: emp,
				category: 'Normal',
				from_date: date,
				to_date: date,
				submit: 0,
			},
			'employee',
		);
		const leaveApprover = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Leave Application', name: leave.name, field: 'leave_approver' },
			'admin',
		);
		expect(leaveApprover).toBe(cast.manager.email);
	});

	test('HR-LV-014 @regression: Reject leave does not mark On Leave', async ({ request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(12);
		await cleanupDay(request, emp, date, 'admin');

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{
				employee: emp,
				category: 'Normal',
				from_date: date,
				to_date: date,
				submit: 1,
			},
			'employee',
		);
		await e2eCall(
			request,
			'set_leave_status',
			{ name: leave.name, status: 'Rejected' },
			'manager',
		);

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
