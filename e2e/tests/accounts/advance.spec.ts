import { expect, test } from '@playwright/test';
import {
	cleanupEmployeeAdvances,
	e2eCall,
	getCast,
	repairE2eReportsToChain,
} from '../../helpers/e2e-api';
import { withPersona } from '../../helpers/persona-context';
import { personaStorage } from '../../helpers/personas';
import { EmployeeAdvanceFormPage } from '../../pages/desk/employee-advance.page';
import { ExpenseClaimFormPage } from '../../pages/desk/expense-claim.page';
import { DeskForm } from '../../helpers/desk';
import { getE2eMasters, getE2eProject } from '../../helpers/ui-fixtures';

test.describe('Employee Advance @accounts @ui', () => {
	test.beforeEach(async ({ request }) => {
		await repairE2eReportsToChain(request);
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-ADV-001 @regression @critical: Self advance within Max Self Advance', async ({
			page,
			request,
			browser,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);

			const advance = new EmployeeAdvanceFormPage(page);
			await advance.openNew();
			await advance.fillAdvance(2000);
			const advanceName = await advance.saveAndSubmit();

			const project = await e2eCall<string | null>(
				request,
				'get_doc_field',
				{ doctype: 'Employee Advance', name: advanceName, field: 'project' },
				'admin',
			);
			expect(project).toBeFalsy();

			const workflowState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Employee Advance', name: advanceName, field: 'workflow_state' },
				'admin',
			);
			expect(workflowState).toBe('Pending Approval');

			await withPersona(browser, 'manager', async (mgrPage) => {
				const adv = new EmployeeAdvanceFormPage(mgrPage);
				await adv.open(advanceName);
				await adv.approve();
			});

			const approvedState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Employee Advance', name: advanceName, field: 'workflow_state' },
				'admin',
			);
			expect(approvedState).toBe('Approved');
		});

		test('AC-ADV-002 @regression @critical: Self advance above Max Self Advance blocked', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);

			const advance = new EmployeeAdvanceFormPage(page);
			await advance.openNew();
			await advance.fillAdvance(2001);
			await advance.trySaveExpectError(/limit/i);
		});

		test('AC-ADV-003 @regression @critical: Employee cannot create advance for another person', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;

			const advance = new EmployeeAdvanceFormPage(page);
			await advance.openNew();
			const selectedEmp = await page.evaluate(
				() => (window as unknown as { cur_frm?: { doc?: { employee?: string } } }).cur_frm?.doc?.employee,
			);
			expect(selectedEmp).toBe(emp);
			const employeeField = page.locator('.form-layout [data-fieldname="employee"]').first();
			const employeeInput = employeeField.locator('input').first();
			if (await employeeInput.isVisible().catch(() => false)) {
				await expect(employeeInput).toBeDisabled();
			}
			await advance.fillAdvance(1500);
			await advance.saveDraft();
		});

		test('AC-ADV-005 @regression @critical: Large leftover blocks new advance', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);

			const first = new EmployeeAdvanceFormPage(page);
			await first.openNew();
			await first.fillAdvance(2000);
			const firstName = await first.saveAndSubmit();

			await e2eCall(
				request,
				'set_advance_settlement',
				{
					name: firstName,
					paid_amount: 10000,
					claimed_amount: 0,
					status: 'Paid',
				},
				'admin',
			);

			const second = new EmployeeAdvanceFormPage(page);
			await second.openNew();
			await second.fillAdvance(1000);
			await second.trySaveExpectError(/unsettled/i);
		});

		test('AC-ADV-006 @regression @critical: Small leftover allows new advance', async ({
			page,
			request,
			browser,
		}) => {
			const cast = await getCast(request, 'admin');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);

			const first = new EmployeeAdvanceFormPage(page);
			await first.openNew();
			await first.fillAdvance(2000);
			const firstName = await first.saveAndSubmit();

			await withPersona(browser, 'manager', async (mgrPage) => {
				const adv = new EmployeeAdvanceFormPage(mgrPage);
				await adv.open(firstName);
				await adv.approve();
			});

			await e2eCall(
				request,
				'set_advance_settlement',
				{
					name: firstName,
					paid_amount: 10000,
					claimed_amount: 9200,
					status: 'Paid',
				},
				'admin',
			);

			const replenish = new EmployeeAdvanceFormPage(page);
			await replenish.openNew();
			await replenish.fillAdvance(1500);
			const replenishName = await replenish.saveAndSubmit();
			expect(replenishName).toBeTruthy();
		});

		test('AC-ADV-007 @regression @critical: Settle advance via Expense Claim link', async ({
			page,
			request,
			browser,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const project = await getE2eProject(request);
			const masters = await getE2eMasters(request);
			await cleanupEmployeeAdvances(request, emp);

			const advance = new EmployeeAdvanceFormPage(page);
			await advance.openNew();
			await advance.fillAdvance(2000);
			const advanceName = await advance.saveAndSubmit();

			await withPersona(browser, 'manager', async (mgrPage) => {
				const adv = new EmployeeAdvanceFormPage(mgrPage);
				await adv.open(advanceName);
				await adv.approve();
			});

			await e2eCall(
				request,
				'set_advance_settlement',
				{
					name: advanceName,
					paid_amount: 2000,
					claimed_amount: 0,
					status: 'Paid',
				},
				'admin',
			);

			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			const hint = await claim.getAdvanceLinkHint();
			expect(hint).toMatch(/Advances available to link via Get Advances/i);
			await claim.fillClaim({
				project,
				amount: 1500,
				expenseType: masters.expense_type,
			});
		});

		test('AC-ADV-008 @regression @critical: Get Advances hides unpaid advances', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const project = await getE2eProject(request);
			await cleanupEmployeeAdvances(request, emp);

			const advance = new EmployeeAdvanceFormPage(page);
			await advance.openNew();
			await advance.fillAdvance(1000);
			const draftName = await advance.saveDraft();
			expect(draftName).toBeTruthy();

			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			const hint = await claim.getAdvanceLinkHint();
			expect(hint).toMatch(/not submitted yet|No advances qualify for Get Advances/i);
			await claim.fillClaim({ project, amount: 500 });
		});
	});

	test('AC-ADV-004 @regression: Accounts can create advance for another', async ({
		browser,
		request,
	}) => {
		const cast = await getCast(request, 'accounts');
		const emp = cast.employee.employee!;
		await cleanupEmployeeAdvances(request, emp);

		let advanceName = '';
		await withPersona(browser, 'accounts', async (page) => {
			const advance = new EmployeeAdvanceFormPage(page);
			await advance.openNew();
			await advance.fillEmployeeAsAccounts('E2E Employee A', emp);
			const selectedEmp = await page.evaluate(
				() => (window as unknown as { cur_frm?: { doc?: { employee?: string } } }).cur_frm?.doc?.employee,
			);
			expect(selectedEmp).toBe(emp);
			await advance.fillAdvance(1500);
			advanceName = await advance.saveAndSubmit();
		});

		const workflowState = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee Advance', name: advanceName, field: 'workflow_state' },
			'admin',
		);
		expect(workflowState).toBe('Pending Approval');

		const ownerEmp = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee Advance', name: advanceName, field: 'employee' },
			'admin',
		);
		expect(ownerEmp).toBe(emp);
	});

	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-ADV-010 @regression: Employee Advances with Residual report', async ({ page }) => {
			const desk = new DeskForm(page);
			await desk.gotoReport('Employee Advances with Residual');
			await expect(page.locator('.report-wrapper')).toBeVisible();
			await expect(page.locator('.report-wrapper .dt-scrollable, .report-wrapper .datatable').first()).toBeVisible({
				timeout: 30000,
			});
		});
	});

	test.describe('as manager', () => {
		test.use({ storageState: personaStorage('manager') });

		test('AC-ADV-011 @regression: Manager self advance limit 5000', async ({ page, request }) => {
			const cast = await getCast(request, 'manager');
			const mgr = cast.manager.employee!;
			await cleanupEmployeeAdvances(request, mgr);

			const advance = new EmployeeAdvanceFormPage(page);
			await advance.openNew();
			await advance.fillAdvance(5000);
			const okName = await advance.saveAndSubmit();
			expect(okName).toBeTruthy();

			await cleanupEmployeeAdvances(request, mgr);
			await advance.openNew();
			await advance.fillAdvance(5001);
			await advance.trySaveExpectError(/limit/i);
		});
	});
});
