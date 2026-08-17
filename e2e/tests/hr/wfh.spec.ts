import { expect, test } from '@playwright/test';
import {
	cleanupDay,
	e2eCall,
	expectErrorContains,
	getCast,
	workingDayFromToday,
} from '../../helpers/e2e-api';

test.describe('HR Work From Home @hr', () => {
	test('HR-WFH-001 @regression @critical: Request WFH and manager approves', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(3);
		await cleanupDay(request, emp, date, 'admin');

		const wfh = await e2eCall<{ name: string; docstatus: number }>(
			request,
			'create_wfh_request',
			{ employee: emp, date, submit: 0 },
			'employee',
		);
		expect(wfh.docstatus).toBe(0);

		await e2eCall(request, 'approve_wfh', { name: wfh.name }, 'manager');

		const docstatus = await e2eCall<number>(
			request,
			'get_doc_field',
			{ doctype: 'Attendance Request', name: wfh.name, field: 'docstatus' },
			'admin',
		);
		expect(docstatus).toBe(1);
	});

	test('HR-WFH-002 @regression @critical: Employee cannot approve own WFH', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(7);
		await cleanupDay(request, emp, date, 'admin');

		const wfh = await e2eCall<{ name: string }>(
			request,
			'create_wfh_request',
			{ employee: emp, date, submit: 0 },
			'employee',
		);

		let blocked = false;
		try {
			await e2eCall(request, 'approve_wfh', { name: wfh.name }, 'employee');
		} catch {
			blocked = true;
		}
		expect(blocked).toBe(true);
	});

	test('HR-WFH-003 @regression @critical: Approved WFH and hours logged yields Work From Home', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-1);
		await cleanupDay(request, emp, date, 'admin');

		const wfh = await e2eCall<{ name: string }>(
			request,
			'create_wfh_request',
			{ employee: emp, date, submit: 0 },
			'employee',
		);
		await e2eCall(request, 'approve_wfh', { name: wfh.name }, 'manager');

		await e2eCall(
			request,
			'create_dwl',
			{ employee: emp, date, hours: 6, submit: 1, is_wfh: 1 },
			'employee',
		);

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Work From Home');
	});

	test('HR-WFH-004 @regression @critical: Approved WFH without hours marks Absent after job', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, emp, date, 'admin');

		const wfh = await e2eCall<{ name: string }>(
			request,
			'create_wfh_request',
			{ employee: emp, date, submit: 0 },
			'employee',
		);
		await e2eCall(request, 'approve_wfh', { name: wfh.name }, 'manager');

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Absent');
	});

	test('HR-WFH-005 @regression @critical: WFH tick without approval blocked', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-1);
		await cleanupDay(request, emp, date, 'admin');

		const res = await e2eCall<{ ok: boolean; error?: string }>(
			request,
			'try_create_dwl',
			{ employee: emp, date, hours: 6, submit: 1, is_wfh: 1 },
			'employee',
		);
		expect(res.ok).toBe(false);
		expectErrorContains(res.error || '', 'approved');
	});

	test('HR-WFH-006 @regression: Manager cancel blocks WFH-ticked work log', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(9);
		await cleanupDay(request, emp, date, 'admin');

		const wfh = await e2eCall<{ name: string }>(
			request,
			'create_wfh_request',
			{ employee: emp, date, submit: 0 },
			'employee',
		);
		await e2eCall(request, 'approve_wfh', { name: wfh.name }, 'manager');
		await e2eCall(request, 'cancel_wfh', { name: wfh.name }, 'manager');

		const res = await e2eCall<{ ok: boolean; error?: string }>(
			request,
			'try_create_dwl',
			{ employee: emp, date, hours: 6, submit: 1, is_wfh: 1 },
			'employee',
		);
		expect(res.ok).toBe(false);
		expectErrorContains(res.error || '', 'approved');
	});
});
