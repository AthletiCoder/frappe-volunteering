import { expect, test } from '@playwright/test';
import { e2eCall, getCast } from '../../helpers/e2e-api';
import { callMethod } from '../../helpers/frappe';
import { personaStorage } from '../../helpers/personas';

test.describe('Expense Claim @accounts', () => {
	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-CLM-001 @regression @critical: Reimbursement happy path to Approved', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const claim = await e2eCall<{ name: string; workflow_state: string }>(
				request,
				'create_expense_claim',
				{ employee: emp, amount: 1500, submit: 1 },
				'employee',
			);
			expect(claim.workflow_state).toBe('Pending Approval');

			const approved = await e2eCall<{ workflow_state: string; docstatus: number }>(
				request,
				'workflow_action',
				{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
				'manager',
			);
			expect(approved.workflow_state).toBe('Approved');
			expect(approved.docstatus).toBe(1);
		});

		test('AC-CLM-002 @regression @critical: Monthly Reimbursement Cap blocks excess', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee_b');
			const emp = cast.employee_b.employee!;
			await e2eCall(request, 'cleanup_expense_claims', { employee: emp }, 'admin');
			await e2eCall(
				request,
				'set_single_setting',
				{
					doctype: 'Volunteering Accounting Settings',
					field: 'monthly_reimbursement_cap',
					value: 3000,
				},
				'admin',
			);
			try {
				await e2eCall(
					request,
					'create_expense_claim',
					{ employee: emp, amount: 2500, submit: 1 },
					'employee_b',
				);
				let blocked = false;
				try {
					await e2eCall(
						request,
						'create_expense_claim',
						{ employee: emp, amount: 1000, submit: 1 },
						'employee_b',
					);
				} catch (error) {
					blocked = true;
					expect(String(error).toLowerCase()).toMatch(/cap|exceed/);
				}
				expect(blocked).toBe(true);
			} finally {
				await e2eCall(
					request,
					'set_single_setting',
					{
						doctype: 'Volunteering Accounting Settings',
						field: 'monthly_reimbursement_cap',
						value: 0,
					},
					'admin',
				);
			}
		});

		test('AC-CLM-003 @regression: Monthly Reimbursement Cap 0 = unlimited', async ({
			request,
		}) => {
			const cast = await getCast(request, 'associate');
			const emp = cast.associate.employee!;
			await e2eCall(
				request,
				'set_single_setting',
				{
					doctype: 'Volunteering Accounting Settings',
					field: 'monthly_reimbursement_cap',
					value: 0,
				},
				'admin',
			);
			await e2eCall(
				request,
				'create_expense_claim',
				{ employee: emp, amount: 1500, submit: 1 },
				'associate',
			);
			const second = await e2eCall<{ workflow_state: string }>(
				request,
				'create_expense_claim',
				{ employee: emp, amount: 1500, submit: 1 },
				'associate',
			);
			expect(second.workflow_state).toBe('Pending Approval');
		});

		test('AC-CLM-005 @regression: Claim requires receipts before submit', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const draft = await e2eCall<{ name: string }>(
				request,
				'create_expense_claim',
				{ employee: emp, amount: 1200, submit: 0 },
				'employee',
			);
			const files = await callMethod<Array<{ name: string }>>(
				request,
				'frappe.client.get_list',
				{
					doctype: 'File',
					filters: {
						attached_to_doctype: 'Expense Claim',
						attached_to_name: draft.name,
					},
					fields: ['name'],
				},
				'admin',
			);
			for (const file of files) {
				await callMethod(
					request,
					'frappe.client.delete',
					{ doctype: 'File', name: file.name },
					'admin',
				);
			}

			const res = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_workflow_action',
				{ doctype: 'Expense Claim', name: draft.name, action: 'Submit' },
				'employee',
			);
			expect(res.ok).toBe(false);
			expect(res.error).toBeTruthy();
		});
	});

	test('AC-CLM-004 @regression: Reject expense claim', async ({ request }) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const claim = await e2eCall<{ name: string }>(
			request,
			'create_expense_claim',
			{ employee: emp, amount: 1200, submit: 1 },
			'employee',
		);
		const rejected = await e2eCall<{ workflow_state: string }>(
			request,
			'workflow_action',
			{ doctype: 'Expense Claim', name: claim.name, action: 'Reject' },
			'manager',
		);
		expect(rejected.workflow_state).toBe('Rejected');

		const payAttempt = await e2eCall<{ ok: boolean }>(
			request,
			'try_workflow_action',
			{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
			'accounts',
		);
		expect(payAttempt.ok).toBe(false);
	});
});
