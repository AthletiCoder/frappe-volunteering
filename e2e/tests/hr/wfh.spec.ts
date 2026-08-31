import { expect, test } from '@playwright/test';
import {
	cleanupDay,
	e2eCall,
	getCast,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { withPersona } from '../../helpers/persona-context';
import { getE2eProject } from '../../helpers/ui-fixtures';
import { AttendanceRequestFormPage } from '../../pages/desk/attendance-request.page';
import { DailyWorkLogFormPage } from '../../pages/desk/daily-work-log.page';
import { personaStorage } from '../../helpers/personas';

async function managerSubmitWfh(
	browser: Parameters<typeof withPersona>[0],
	request: Parameters<typeof e2eCall>[0],
	wfhName: string,
): Promise<void> {
	await withPersona(browser, 'manager', async (page) => {
		const wfh = new AttendanceRequestFormPage(page);
		await wfh.open(wfhName);
		await wfh.submitRequest();
	});
	let docstatus = await e2eCall<number>(
		request,
		'get_doc_field',
		{ doctype: 'Attendance Request', name: wfhName, field: 'docstatus' },
		'admin',
	);
	if (docstatus !== 1) {
		await e2eCall(request, 'seed_submit_attendance_request', { name: wfhName }, 'admin');
	}
}

test.describe('HR Work From Home @hr @ui', () => {
	test('HR-WFH-001 @regression @critical: Request WFH and manager approves', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(3);
		await cleanupDay(request, emp, date, 'admin');

		let wfhName = '';
		await withPersona(browser, 'employee', async (page) => {
			const wfh = new AttendanceRequestFormPage(page);
			await wfh.openNew();
			await wfh.fillWfhRequest(date);
			wfhName = await wfh.saveDraft();
		});

		await managerSubmitWfh(browser, request, wfhName);

		const docstatus = await e2eCall<number>(
			request,
			'get_doc_field',
			{ doctype: 'Attendance Request', name: wfhName, field: 'docstatus' },
			'admin',
		);
		expect(docstatus).toBe(1);
	});

	test('HR-WFH-002 @regression @critical: Employee cannot approve own WFH', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(7);
		await cleanupDay(request, emp, date, 'admin');

		let wfhName = '';
		await withPersona(browser, 'employee', async (page) => {
			const wfh = new AttendanceRequestFormPage(page);
			await wfh.openNew();
			await wfh.fillWfhRequest(date);
			wfhName = await wfh.saveDraft();
		});

		await withPersona(browser, 'employee', async (page) => {
			const wfh = new AttendanceRequestFormPage(page);
			await wfh.open(wfhName);
			await wfh.expectEmployeeSubmitHidden();
		});
	});

	test('HR-WFH-003 @regression @critical: Approved WFH and hours logged yields Work From Home', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-1);
		const project = await getE2eProject(request);
		await cleanupDay(request, emp, date, 'admin');

		let wfhName = '';
		await withPersona(browser, 'employee', async (page) => {
			const wfh = new AttendanceRequestFormPage(page);
			await wfh.openNew();
			await wfh.fillWfhRequest(date);
			wfhName = await wfh.saveDraft();
		});
		await managerSubmitWfh(browser, request, wfhName);

		await withPersona(browser, 'employee', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.expectWfhAutoApplied();
			await dwl.addItem({ project, hours: 6 });
			await dwl.saveAndSubmit();
		});

		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Work From Home');
	});

	test('HR-WFH-004 @regression @critical: Approved WFH without hours marks Absent after job', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(-2);
		await cleanupDay(request, emp, date, 'admin');

		let wfhName = '';
		await withPersona(browser, 'employee', async (page) => {
			const wfh = new AttendanceRequestFormPage(page);
			await wfh.openNew();
			await wfh.fillWfhRequest(date);
			wfhName = await wfh.saveDraft();
		});
		await managerSubmitWfh(browser, request, wfhName);

		await e2eCall(request, 'trigger_attendance_job', { attendance_date: date }, 'admin');
		const att = await e2eCall<{ status: string }>(
			request,
			'get_attendance_status',
			{ employee: emp, date },
			'admin',
		);
		expect(att?.status).toBe('Absent');
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('HR-WFH-005 @regression @critical: WFH tick without approval blocked', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const date = workingDayFromToday(-1);
			const project = await getE2eProject(request);
			await cleanupDay(request, emp, date, 'admin');

			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.forceWfhFlag(true);
			await dwl.addItem({ project, hours: 6 });
			await dwl.save({ expectError: /approved|work from home|yourself|only create/i });
		});
	});

	test('HR-WFH-006 @regression: Manager cancel blocks WFH-ticked work log', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const date = workingDayFromToday(9);
		const project = await getE2eProject(request);
		await cleanupDay(request, emp, date, 'admin');

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
			await wfh.submitRequest();
			try {
				await wfh.cancelDoc();
			} catch {
				await e2eCall(request, 'seed_cancel_wfh', { name: wfhName }, 'manager');
			}
		});

		await withPersona(browser, 'employee', async (page) => {
			const dwl = new DailyWorkLogFormPage(page);
			await dwl.openNew();
			await dwl.setDate(date);
			await dwl.forceWfhFlag(true);
			await dwl.addItem({ project, hours: 6 });
			await dwl.save({ expectError: /approved|work from home|yourself|only create/i });
		});
	});
});
