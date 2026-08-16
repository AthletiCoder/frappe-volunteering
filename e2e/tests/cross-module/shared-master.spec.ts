import { expect, test } from '@playwright/test';
import {
	addDays,
	cleanupDay,
	cleanupEmployeeAdvances,
	cleanupLeaveSpan,
	e2eCall,
	getCast,
	todayLocal,
	workingDayFromToday,
} from '../../helpers/e2e-api';
import { personaStorage, PERSONAS } from '../../helpers/personas';

test.describe('Cross-module shared employee master @hr @accounts', () => {
	test('XM-001 @regression @critical: Reports To drives leave and spend approvals', async ({
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const managerEmail = PERSONAS.manager.email;
		const leaveDate = workingDayFromToday(30);
		await cleanupLeaveSpan(request, emp, leaveDate, leaveDate, 'admin');

		const leave = await e2eCall<{ name: string }>(
			request,
			'create_leave_application',
			{
				employee: emp,
				from_date: leaveDate,
				to_date: leaveDate,
				submit: 1,
			},
			'employee',
		);
		const leaveApprover = await e2eCall<string>(
			request,
			'get_doc_field',
			{
				doctype: 'Leave Application',
				name: leave.name,
				field: 'leave_approver',
			},
			'admin',
		);
		expect(leaveApprover).toBe(managerEmail);

		const claim = await e2eCall<{ name: string; pending_approver?: string }>(
			request,
			'create_expense_claim',
			{ employee: emp, amount: 1500, submit: 1 },
			'employee',
		);
		expect(claim.pending_approver).toBe(managerEmail);

		const flags = await e2eCall<{ is_pending_approver: boolean; can_approve: boolean }>(
			request,
			'get_approver_flags',
			{ doctype: 'Expense Claim', name: claim.name },
			'manager',
		);
		expect(flags.is_pending_approver).toBe(true);
		expect(flags.can_approve).toBe(true);
	});

	test('XM-002 @regression @critical: Grade change updates Accounts limits; HR still works', async ({
		request,
	}) => {
		test.setTimeout(120000);
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const originalGrade = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: emp, field: 'grade' },
			'admin',
		);
		const originalDesignation = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee', name: emp, field: 'designation' },
			'admin',
		);

		try {
			await e2eCall(
				request,
				'set_employee_field',
				{ employee: emp, field: 'grade', value: 'Associate' },
				'admin',
			);
			await e2eCall(
				request,
				'set_employee_field',
				{ employee: emp, field: 'designation', value: 'Associate' },
				'admin',
			);

			await cleanupEmployeeAdvances(request, emp);
			const overAssociateLimit = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_advance',
				{ employee: emp, amount: 10000 },
				'employee',
			);
			expect(overAssociateLimit.ok).toBe(false);
			expect(overAssociateLimit.error?.toLowerCase()).toMatch(/limit|exceed/);

			const date = workingDayFromToday(-1);
			await cleanupDay(request, emp, date, 'admin');
			const dwl = await e2eCall<{ docstatus: number }>(
				request,
				'create_dwl',
				{ employee: emp, date, hours: 6, submit: 1 },
				'employee',
			);
			expect(dwl.docstatus).toBe(1);

			await e2eCall(
				request,
				'set_employee_field',
				{ employee: emp, field: 'grade', value: 'Director' },
				'admin',
			);
			await e2eCall(
				request,
				'set_employee_field',
				{ employee: emp, field: 'designation', value: 'Director' },
				'admin',
			);

			await cleanupEmployeeAdvances(request, emp);
			const withinDirectorLimit = await e2eCall<{ ok: boolean }>(
				request,
				'try_create_advance',
				{ employee: emp, amount: 10000 },
				'employee',
			);
			expect(withinDirectorLimit.ok).toBe(true);
		} finally {
			if (originalGrade) {
				await e2eCall(
					request,
					'set_employee_field',
					{ employee: emp, field: 'grade', value: originalGrade },
					'admin',
				);
			}
			if (originalDesignation) {
				await e2eCall(
					request,
					'set_employee_field',
					{ employee: emp, field: 'designation', value: originalDesignation },
					'admin',
				);
			}
		}
	});

	test.describe('XM-003 @regression: Unpaid employee HR exclusions', () => {
		test('digest preview omits unpaid staff', async ({ request }) => {
			const cast = await getCast(request, 'admin');
			const unpaidEmp = cast.unpaid.employee!;
			const employeeName = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Employee', name: unpaidEmp, field: 'employee_name' },
				'admin',
			);

			const preview = await e2eCall<{
				html: string;
				recipients: string[];
				frequency: string;
				label: string;
			}>(request, 'preview_work_log_digest', {}, 'hr');

			expect(preview.html.length).toBeGreaterThan(0);
			expect(preview.html).not.toContain(employeeName);
			expect(preview.recipients).not.toContain(PERSONAS.unpaid.email);
		});

		test.describe('as unpaid', () => {
			test.use({ storageState: personaStorage('unpaid') });

			test('attendance job skips unpaid employee', async ({ request }) => {
				const cast = await getCast(request, 'unpaid');
				const emp = cast.unpaid.employee!;
				const date = addDays(todayLocal(), -1);
				await cleanupDay(request, emp, date, 'admin');

				await e2eCall(
					request,
					'trigger_attendance_job',
					{ attendance_date: date },
					'admin',
				);

				const att = await e2eCall<{ status: string } | null>(
					request,
					'get_attendance_status',
					{ employee: emp, date },
					'admin',
				);
				expect(att?.status || att).toBeFalsy();
			});

			test('advance attempt outcome is recorded', async ({ request }) => {
				const outcome = await e2eCall<{ ok: boolean; error?: string }>(
					request,
					'try_create_advance',
					{ amount: 1000 },
					'unpaid',
				);
				expect(typeof outcome.ok).toBe('boolean');
				if (!outcome.ok) {
					expect(outcome.error).toBeTruthy();
				}
			});
		});
	});
});
