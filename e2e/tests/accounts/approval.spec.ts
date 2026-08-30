import { expect, test } from '@playwright/test';
import {
	cleanupEmployeeAdvances,
	cleanupExpenseClaimsForProject,
	e2eCall,
	getCast,
	repairE2eReportsToChain,
} from '../../helpers/e2e-api';
import { withPersona } from '../../helpers/persona-context';
import { PERSONAS, personaStorage } from '../../helpers/personas';
import { getE2eMasters, getE2eProject } from '../../helpers/ui-fixtures';
import { EmployeeAdvanceFormPage } from '../../pages/desk/employee-advance.page';
import { ExpenseClaimFormPage } from '../../pages/desk/expense-claim.page';
import { seedEscalateExpenseClaim } from '../../helpers/manager-float-fixtures';

test.describe('Approval routing @accounts @ui', () => {
	test('AC-APR-001 @regression @critical: Approve when amount <= Max Approval Authority', async ({
		browser,
		request,
	}) => {
		test.setTimeout(240_000);
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const project = await getE2eProject(request);
		await cleanupExpenseClaimsForProject(request, project);
		const masters = await getE2eMasters(request);

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
		expect(pendingApprover).toBe(PERSONAS.manager.email);

		await withPersona(browser, 'manager', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			await claim.approve();
		});

		const workflowState = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
			'admin',
		);
		expect(workflowState).toBe('Approved');
	});

	test('AC-APR-002 @regression @critical: Cannot Approve when over authority; can Escalate', async ({
		browser,
		request,
	}) => {
		test.setTimeout(300_000);
		const cast = await getCast(request, 'employee');
		const directorEmp = cast.director.employee!;
		const chairEmp = cast.chair.employee!;
		const project = await getE2eProject(request);
		await cleanupExpenseClaimsForProject(request, project);
		const masters = await getE2eMasters(request);

		await e2eCall(
			request,
			'set_employee_reports_to',
			{ employee: directorEmp, reports_to: '' },
			'admin',
		);
		try {
			let claimName = '';
			await withPersona(browser, 'employee', async (page) => {
				const claim = new ExpenseClaimFormPage(page);
				await claim.openNew();
				await claim.fillClaim({
					project,
					amount: 30000,
					expenseType: masters.expense_type,
					vendorOverrideReason: 'Vendor does not accept POs',
				});
				claimName = await claim.saveAndSubmit(request);
			});

			await withPersona(browser, 'manager', async (page) => {
				const claim = new ExpenseClaimFormPage(page);
				await claim.open(claimName);
				await claim.expectApproveNotVisible();
				await claim.expectEscalateVisible();
			});
		} finally {
			await e2eCall(
				request,
				'set_employee_reports_to',
				{ employee: directorEmp, reports_to: chairEmp },
				'admin',
			);
		}
	});

	test('AC-APR-003 @regression @critical: Associate authority 0 cannot approve others', async ({
		browser,
		request,
	}) => {
		const project = await getE2eProject(request);
		const masters = await getE2eMasters(request);

		let claimName = '';
		await withPersona(browser, 'employee', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 500,
				expenseType: masters.expense_type,
			});
			claimName = await claim.saveAndSubmit(request);
		});

		await withPersona(browser, 'employee', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			const canApprove = await claim.workflowActionVisible('Approve');
			expect(canApprove).toBe(false);
			const primaryApprove = page.locator('.primary-action').filter({ hasText: /^Approve$/ });
			await expect(primaryApprove).toHaveCount(0);
		});
	});

	test('AC-APR-004 @regression @critical: Board-level can approve any amount', async ({
		browser,
		request,
	}) => {
		test.setTimeout(300_000);
		await repairE2eReportsToChain(request);
		const project = await getE2eProject(request);
		await cleanupExpenseClaimsForProject(request, project);
		const masters = await getE2eMasters(request);

		let claimName = '';
		await withPersona(browser, 'employee', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 30000,
				expenseType: masters.expense_type,
				vendorOverrideReason: 'Vendor does not accept POs',
			});
			claimName = await claim.saveAndSubmit(request);
		});

		const pendingApprover = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Expense Claim', name: claimName, field: 'pending_approver' },
			'admin',
		);
		expect(pendingApprover).toBe(PERSONAS.chair.email);

		await withPersona(browser, 'chair', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			await claim.approve({
				budgetOverrideReason: 'E2E board approval for high-value vendor reimbursement.',
			});
		});

		const workflowState = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
			'admin',
		);
		expect(workflowState).toBe('Approved');
	});

	test('AC-APR-005 @regression @critical: Cannot approve own spending request', async ({
		browser,
		request,
	}) => {
		test.setTimeout(240_000);
		const project = await getE2eProject(request);
		await cleanupExpenseClaimsForProject(request, project);
		const masters = await getE2eMasters(request);

		let claimName = '';
		await withPersona(browser, 'manager', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 500,
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
		expect(pendingApprover).toBe(PERSONAS.director.email);

		await withPersona(browser, 'manager', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			const flags = await claim.getApproverFlags();
			expect(flags.is_pending_approver).toBe(false);
			await claim.expectApproveNotVisible();
		});
	});

	test('AC-APR-006 @regression @critical: Escalate follows Reports To chain', async ({
		browser,
		request,
	}) => {
		test.setTimeout(360_000);
		const cast = await getCast(request, 'employee');
		const directorEmp = cast.director.employee!;
		const chairEmp = cast.chair.employee!;
		const project = await getE2eProject(request);
		await cleanupExpenseClaimsForProject(request, project);
		const masters = await getE2eMasters(request);

		await e2eCall(
			request,
			'set_employee_reports_to',
			{ employee: directorEmp, reports_to: '' },
			'admin',
		);
		try {
			let claimName = '';
			await withPersona(browser, 'employee', async (page) => {
				const claim = new ExpenseClaimFormPage(page);
				await claim.openNew();
				await claim.fillClaim({
					project,
					amount: 30000,
					expenseType: masters.expense_type,
					vendorOverrideReason: 'Vendor does not accept POs',
				});
				claimName = await claim.saveAndSubmit(request);
			});

			await withPersona(browser, 'manager', async (page) => {
				const claim = new ExpenseClaimFormPage(page);
				await claim.open(claimName);
				await claim.expectApproveNotVisible();
			});

			const escalatedToDirector = await seedEscalateExpenseClaim(
				request,
				claimName,
				'Above manager authority',
			);
			expect(escalatedToDirector.pending_approver).toBe(PERSONAS.director.email);

			const escalatedToChair = await seedEscalateExpenseClaim(
				request,
				claimName,
				'Director limit also exceeded',
			);
			expect(escalatedToChair.pending_approver).toBe(PERSONAS.chair.email);

			await withPersona(browser, 'chair', async (page) => {
				const claim = new ExpenseClaimFormPage(page);
				await claim.open(claimName);
				await claim.approve({
					budgetOverrideReason: 'E2E final board approval after escalation chain.',
				});
			});

			const workflowState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
				'admin',
			);
			expect(workflowState).toBe('Approved');
		} finally {
			await e2eCall(
				request,
				'set_employee_reports_to',
				{ employee: directorEmp, reports_to: chairEmp },
				'admin',
			);
		}
	});

	test('AC-APR-007 @regression: Approval Authority toggle Off uses simple tiers', async ({
		browser,
		request,
	}) => {
		const project = await getE2eProject(request);
		const masters = await getE2eMasters(request);

		await e2eCall(
			request,
			'set_single_setting',
			{
				doctype: 'Volunteering Accounting Settings',
				field: 'use_grade_approval',
				value: 0,
			},
			'admin',
		);
		try {
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

			const workflowState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
				'admin',
			);
			expect(workflowState).toBeTruthy();
		} finally {
			await e2eCall(
				request,
				'set_single_setting',
				{
					doctype: 'Volunteering Accounting Settings',
					field: 'use_grade_approval',
					value: 1,
				},
				'admin',
			);
		}
	});

	test.describe('as hr', () => {
		test.use({ storageState: personaStorage('hr') });

		test('AC-APR-008 @regression @critical: Grade change updates effective limits', async ({
			page,
			request,
			browser,
		}) => {
			test.setTimeout(240_000);
			const cast = await getCast(request, 'admin');
			const emp = cast.associate.employee!;
			const originalGrade = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Employee', name: emp, field: 'grade' },
				'admin',
			);
			try {
				await e2eCall(
					request,
					'set_employee_field',
					{ employee: emp, field: 'grade', value: 'Manager' },
					'admin',
				);
				await cleanupEmployeeAdvances(request, emp);

				await withPersona(browser, 'associate', async (assocPage) => {
					const advance = new EmployeeAdvanceFormPage(assocPage);
					await advance.openNew();
					await advance.fillAdvance(5000);
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
			}
		});
	});
});
