import { expect, test } from '@playwright/test';
import {
	cleanupExpenseClaimsForProject,
	e2eCall,
	getFixtures,
	repairE2eReportsToChain,
} from '../../helpers/e2e-api';
import { withPersona } from '../../helpers/persona-context';
import { PERSONAS } from '../../helpers/personas';
import { getE2eMasters, getE2eProject } from '../../helpers/ui-fixtures';
import { ExpenseClaimFormPage } from '../../pages/desk/expense-claim.page';

test.describe('Budget controls @accounts @ui', () => {
	test('AC-BUD-001 @regression: Soft budget warning near budget', async ({ browser, request }) => {
		const fixtures = await getFixtures(request, 'admin');
		const project = await getE2eProject(request);
		const masters = await getE2eMasters(request);

		await e2eCall(
			request,
			'set_single_setting',
			{
				doctype: 'Volunteering Accounting Settings',
				field: 'enable_budget_warnings',
				value: 1,
			},
			'admin',
		);
		await e2eCall(
			request,
			'set_project_budget',
			{
				project: fixtures.project,
				department: fixtures.department,
				allocated_amount: 10000,
			},
			'admin',
		);

		let claimName = '';
		await withPersona(browser, 'employee', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 9000,
				expenseType: masters.expense_type,
				vendorOverrideReason: 'Urgent reimbursement; PO not feasible.',
			});
			claimName = await claim.saveAndSubmit(request, { expectBudgetWarning: true });
		});

		const workflowState = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
			'admin',
		);
		expect(workflowState).toBe('Pending Approval');
	});

	test('AC-BUD-002 @regression @critical: Hard block when overspend exceeds Budget Hard-Block %', async ({
		browser,
		request,
	}) => {
		const fixtures = await getFixtures(request, 'admin');
		const project = await getE2eProject(request);
		const masters = await getE2eMasters(request);
		await repairE2eReportsToChain(request);
		await cleanupExpenseClaimsForProject(request, project);

		await e2eCall(
			request,
			'set_project_budget',
			{
				project: fixtures.project,
				department: fixtures.department,
				allocated_amount: 10000,
			},
			'admin',
		);

		let claimName = '';
		await withPersona(browser, 'employee_b', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 13000,
				expenseType: masters.expense_type,
				vendorOverrideReason: 'Urgent reimbursement; PO not feasible.',
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

		await withPersona(browser, 'director', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			await claim.approveExpectError(/budget|exceed|block/i);
		});
	});

	test('AC-BUD-003 @regression @critical: Budget Override Role can exceed hard block', async ({
		browser,
		request,
	}) => {
		const fixtures = await getFixtures(request, 'admin');
		const project = await getE2eProject(request);
		const masters = await getE2eMasters(request);

		await e2eCall(
			request,
			'set_project_budget',
			{
				project: fixtures.project,
				department: fixtures.department,
				allocated_amount: 10000,
			},
			'admin',
		);

		let claimName = '';
		await withPersona(browser, 'associate', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 30000,
				expenseType: masters.expense_type,
				vendorOverrideReason: 'Urgent reimbursement; PO not feasible.',
				budgetOverrideReason: 'Seasonal campaign overspend approved by dept.',
			});
			claimName = await claim.saveAndSubmit(request);
		});

		await withPersona(browser, 'chair', async (page) => {
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

	test('Expense Claim without project is blocked', async ({ browser, request }) => {
		const masters = await getE2eMasters(request);

		await withPersona(browser, 'employee', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillExpenseRowWithoutProject({
				expenseType: masters.expense_type,
				description: 'Missing project on purpose',
				amount: 500,
			});
			await claim.save({ expectError: /project/i });
		});
	});
});
