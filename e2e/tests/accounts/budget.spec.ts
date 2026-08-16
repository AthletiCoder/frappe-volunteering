import { expect, test } from '@playwright/test';
import { e2eCall, getCast, getFixtures } from '../../helpers/e2e-api';

test.describe('Budget controls @accounts', () => {
	test('AC-BUD-001 @regression: Soft budget warning near budget', async ({ request }) => {
		const fixtures = await getFixtures(request, 'admin');
		const cast = await getCast(request, 'admin');
		const emp = cast.employee.employee!;
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

		const claim = await e2eCall<{ name: string; workflow_state: string }>(
			request,
			'create_expense_claim',
			{
				employee: emp,
				amount: 9000,
				submit: 1,
				vendor_override_reason: 'Urgent reimbursement; PO not feasible.',
			},
			'employee',
		);
		expect(claim.workflow_state).toBe('Pending Approval');
	});

	test('AC-BUD-002 @regression @critical: Hard block when overspend exceeds Budget Hard-Block %', async ({
		request,
	}) => {
		const fixtures = await getFixtures(request, 'admin');
		const cast = await getCast(request, 'admin');
		const emp = cast.employee_b.employee!;
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

		const claim = await e2eCall<{ name: string }>(
			request,
			'create_expense_claim',
			{
				employee: emp,
				amount: 13000,
				submit: 1,
				vendor_override_reason: 'Urgent reimbursement; PO not feasible.',
			},
			'employee',
		);

		const blocked = await e2eCall<{ ok: boolean }>(
			request,
			'try_workflow_action',
			{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
			'manager',
		);
		expect(blocked.ok).toBe(false);
	});

	test('AC-BUD-003 @regression @critical: Budget Override Role can exceed hard block', async ({
		request,
	}) => {
		const fixtures = await getFixtures(request, 'admin');
		const cast = await getCast(request, 'admin');
		const emp = cast.associate.employee!;
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

		const claim = await e2eCall<{ name: string }>(
			request,
			'create_expense_claim',
			{
				employee: emp,
				amount: 30000,
				submit: 1,
				vendor_override_reason: 'Urgent reimbursement; PO not feasible.',
				budget_override_reason: 'Seasonal campaign overspend approved by dept.',
			},
			'associate',
		);

		const approved = await e2eCall<{ workflow_state: string }>(
			request,
			'workflow_action',
			{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
			'chair',
		);
		expect(approved.workflow_state).toBe('Approved');
	});
});
