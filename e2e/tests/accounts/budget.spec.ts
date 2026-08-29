import { expect, test } from '@playwright/test';
import { e2eCall, getFixtures } from '../../helpers/e2e-api';
import { expectFormError } from '../../helpers/dialogs';
import { withPersona } from '../../helpers/persona-context';
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

		await withPersona(browser, 'manager', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			await claim.approve();
			await expectFormError(page, /budget|exceed|block/i);
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
			const rowIndex = await claim.getOrCreateEditableRow('expenses', 'description');
			await claim.fillGridField('expenses', rowIndex, 'expense_type', masters.expense_type);
			await claim.fillGridField('expenses', rowIndex, 'description', 'Missing project on purpose');
			await claim.fillGridField('expenses', rowIndex, 'amount', '500');
			await claim.save();
			await expectFormError(page, /project/i);
		});
	});
});
