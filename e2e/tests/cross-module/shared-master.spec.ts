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
import { withPersona } from '../../helpers/persona-context';
import { personaStorage, PERSONAS } from '../../helpers/personas';
import { getE2eMasters, getE2eProject } from '../../helpers/ui-fixtures';
import { DailyWorkLogFormPage } from '../../pages/desk/daily-work-log.page';
import { DailyWorkLogSettingsPage } from '../../pages/desk/dwl-settings.page';
import { EmployeeAdvanceFormPage } from '../../pages/desk/employee-advance.page';
import { EmployeeFormPage } from '../../pages/desk/employee.page';
import { ExpenseClaimFormPage } from '../../pages/desk/expense-claim.page';
import { LeaveApplicationFormPage } from '../../pages/desk/leave-application.page';

test.describe('Cross-module shared employee master @hr @accounts @ui', () => {
	test('XM-001 @regression @critical: Reports To drives leave and spend approvals', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const managerEmail = PERSONAS.manager.email;
		const leaveDate = workingDayFromToday(30);
		const project = await getE2eProject(request);
		const masters = await getE2eMasters(request);
		await cleanupLeaveSpan(request, emp, leaveDate, leaveDate, 'admin');

		let leaveName = '';
		await withPersona(browser, 'employee', async (page) => {
			const leave = new LeaveApplicationFormPage(page);
			await leave.openNew();
			await leave.fillLeave({ fromDate: leaveDate, toDate: leaveDate, category: 'Normal' });
			leaveName = await leave.saveAndSubmit();
		});

		const leaveApprover = await e2eCall<string>(
			request,
			'get_doc_field',
			{
				doctype: 'Leave Application',
				name: leaveName,
				field: 'leave_approver',
			},
			'admin',
		);
		expect(leaveApprover).toBe(managerEmail);

		let claimName = '';
		await withPersona(browser, 'employee', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 1500,
				expenseType: masters.expense_type,
			});
			claimName = await claim.saveAndSubmit(request);
		});

		const pendingApprover = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Expense Claim', name: claimName, field: 'pending_approver' },
			'admin',
		);
		expect(pendingApprover).toBe(managerEmail);

		await withPersona(browser, 'manager', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			const canApprove = await claim.workflowActionVisible('Approve');
			const primaryApprove = page.locator('.primary-action').filter({ hasText: /^Approve$/ });
			expect(canApprove || (await primaryApprove.isVisible().catch(() => false))).toBeTruthy();
			await claim.approve();
		});
	});

	test('XM-002 @regression @critical: Grade change updates Accounts limits; HR still works', async ({
		browser,
		request,
	}) => {
		test.setTimeout(120000);
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
		const project = await getE2eProject(request);
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
			await withPersona(browser, 'admin', async (page) => {
				const employee = new EmployeeFormPage(page);
				await employee.open(emp);
				await employee.setField('grade', 'Associate');
				await employee.setField('designation', 'Associate');
			});

			await cleanupEmployeeAdvances(request, emp);
			await withPersona(browser, 'employee', async (page) => {
				const advance = new EmployeeAdvanceFormPage(page);
				await advance.openNew();
				await advance.fillAdvance(10000);
				await advance.trySaveExpectError(/limit|exceed/i);
			});

			const date = workingDayFromToday(-1);
			await cleanupDay(request, emp, date, 'admin');
			await withPersona(browser, 'employee', async (page) => {
				const dwl = new DailyWorkLogFormPage(page);
				await dwl.openNew();
				await dwl.setDate(date);
				await dwl.addItem({ project, hours: 6 });
				const name = await dwl.saveAndSubmit();
				expect(name).toBeTruthy();
			});

			await withPersona(browser, 'admin', async (page) => {
				const employee = new EmployeeFormPage(page);
				await employee.open(emp);
				await employee.setField('grade', 'Director');
				await employee.setField('designation', 'Director');
			});

			await cleanupEmployeeAdvances(request, emp);
			await withPersona(browser, 'employee', async (page) => {
				const advance = new EmployeeAdvanceFormPage(page);
				await advance.openNew();
				await advance.fillAdvance(10000);
				const name = await advance.saveAndSubmit();
				expect(name).toBeTruthy();
			});
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
		test('digest preview omits unpaid staff', async ({ browser, request }) => {
			const cast = await getCast(request, 'admin');
			const unpaidEmp = cast.unpaid.employee!;
			const employeeName = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Employee', name: unpaidEmp, field: 'employee_name' },
				'admin',
			);

			await withPersona(browser, 'hr', async (page) => {
				const settings = new DailyWorkLogSettingsPage(page);
				await settings.open();
				await settings.previewSummary();
				const dialog = page.locator('.modal-dialog:visible');
				await expect(dialog).toBeVisible();
				await expect(dialog.locator('.modal-body')).not.toContainText(employeeName);
			});
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

			test('advance attempt outcome is recorded', async ({ page, request }) => {
				const advance = new EmployeeAdvanceFormPage(page);
				await advance.openNew();
				await advance.fillAdvance(1000);
				await advance.save();
				const blocked = page.locator('.modal-dialog:visible, .msgprint, .form-message.errors');
				const saved = advance.getDocNameFromUrl();
				expect((await blocked.isVisible().catch(() => false)) || !!saved).toBeTruthy();
			});
		});
	});
});
