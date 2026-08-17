import { expect, test } from '@playwright/test';
import {
	cleanupDay,
	e2eCall,
	expectErrorContains,
	getCast,
	lastWednesday,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { personaStorage } from '../../helpers/personas';

async function approveRegularization(
	request: Parameters<typeof e2eCall>[0],
	name: string,
): Promise<void> {
	await e2eCall(request, 'approve_regularization', { name }, 'manager');
}

async function rejectRegularization(
	request: Parameters<typeof e2eCall>[0],
	name: string,
): Promise<void> {
	await e2eCall(request, 'reject_regularization', { name }, 'manager');
}

test.describe('HR Attendance @hr', () => {
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
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-1);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');
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

	test('HR-ATT-003 @regression @critical: Holiday takes priority over logged hours', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = lastWednesday();
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(
			request,
			'create_dwl',
			{ employee: emp, date, hours: 6, submit: 1 },
			'employee',
		);
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
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, emp, date, 'admin');

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{
				employee: emp,
				category: 'Emergency',
				from_date: date,
				to_date: date,
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
		await e2eCall(
			request,
			'create_dwl',
			{ employee: emp, date, hours: 8, submit: 1 },
			'employee',
		);
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
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		const req = await e2eCall<{ name: string }>(
			request,
			'create_regularization',
			{
				employee: emp,
				attendance_date: date,
				requested_status: 'Present',
				reason: 'Forgot to log work; hours were actually completed for E2E test.',
			},
			'employee',
		);
		await approveRegularization(request, req.name);

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
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-3);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(
			request,
			'create_regularization',
			{
				employee: emp,
				attendance_date: date,
				requested_status: 'Present',
				reason: 'First open regularization request for duplicate-day E2E test.',
			},
			'employee',
		);

		let blocked = false;
		try {
			await e2eCall(
				request,
				'create_regularization',
				{
					employee: emp,
					attendance_date: date,
					requested_status: 'Half Day',
					reason: 'Second regularization should be blocked on the same date.',
				},
				'employee',
			);
		} catch (err) {
			blocked = true;
			expectErrorContains(String(err), 'already exists');
		}
		expect(blocked).toBe(true);
	});

	test('HR-ATT-007 @regression: Manager rejects regularization', async ({ request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-3);
		await cleanupDay(request, emp, date, 'admin');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		const req = await e2eCall<{ name: string }>(
			request,
			'create_regularization',
			{
				employee: emp,
				attendance_date: date,
				requested_status: 'Present',
				reason: 'Requesting Present after missed log; manager will reject in E2E.',
			},
			'employee',
		);
		await rejectRegularization(request, req.name);

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
		expect(att?.status || att).toBeFalsy();
	});

	test('HR-ATT-009 @regression: Regularization beats approved leave', async ({ request }) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-4);
		await cleanupDay(request, emp, date, 'admin');

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{
				employee: emp,
				category: 'Emergency',
				from_date: date,
				to_date: date,
				submit: 1,
			},
			'hr',
		);
		await e2eCall(
			request,
			'set_leave_status',
			{ name: leave.name, status: 'Approved' },
			'manager',
		);

		const req = await e2eCall<{ name: string }>(
			request,
			'create_regularization',
			{
				employee: emp,
				attendance_date: date,
				requested_status: 'Present',
				reason: 'Approved leave exists but regularization should lock Present status.',
			},
			'employee',
		);
		await approveRegularization(request, req.name);

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
			await page.goto('/desk/attendance', { waitUntil: 'domcontentloaded' });
			await expect(page.locator('body')).toBeVisible();
		});
	});
});
