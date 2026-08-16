import { expect, test } from '@playwright/test';
import {
	cleanupEmployeeAdvances,
	e2eCall,
	expectErrorContains,
	getCast,
} from '../../helpers/e2e-api';
import { callMethod } from '../../helpers/frappe';
import { personaStorage } from '../../helpers/personas';

test.describe('Employee Advance @accounts', () => {
	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-ADV-001 @regression @critical: Self advance within Max Self Advance', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);
			const advance = await e2eCall<{
				name: string;
				workflow_state: string;
			}>(request, 'create_employee_advance', { employee: emp, amount: 2000, submit: 1 }, 'employee');
			expect(advance.workflow_state).toBe('Pending Approval');

			const project = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Employee Advance', name: advance.name, field: 'project' },
				'admin',
			);
			expect(project).toBeTruthy();

			const approved = await e2eCall<{ workflow_state: string }>(
				request,
				'workflow_action',
				{ doctype: 'Employee Advance', name: advance.name, action: 'Approve' },
				'manager',
			);
			expect(approved.workflow_state).toBe('Approved');
		});

		test('AC-ADV-002 @regression @critical: Self advance above Max Self Advance blocked', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);
			const res = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_advance',
				{ employee: emp, amount: 2001 },
				'employee',
			);
			expect(res.ok).toBe(false);
			expectErrorContains(res.error || '', 'limit');
		});

		test('AC-ADV-003 @regression @critical: Employee cannot create advance for another person', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const other = cast.employee_b.employee!;
			const res = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_advance',
				{ employee: other, amount: 1500 },
				'employee',
			);
			expect(res.ok).toBe(false);
			expectErrorContains(res.error || '', 'yourself');
		});

		test('AC-ADV-005 @regression @critical: Large leftover blocks new advance', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);
			await e2eCall(
				request,
				'create_employee_advance',
				{ employee: emp, amount: 2000, submit: 1 },
				'employee',
			);
			const blocked = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_advance',
				{ employee: emp, amount: 1000 },
				'employee',
			);
			expect(blocked.ok).toBe(false);
			expectErrorContains(blocked.error || '', 'unsettled');
		});

		test('AC-ADV-006 @regression @critical: Small leftover allows new advance', async ({
			request,
		}) => {
			const cast = await getCast(request, 'admin');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);
			const first = await e2eCall<{ name: string }>(
				request,
				'create_employee_advance',
				{ employee: emp, amount: 2000, submit: 1 },
				'employee',
			);
			await e2eCall(
				request,
				'workflow_action',
				{ doctype: 'Employee Advance', name: first.name, action: 'Approve' },
				'manager',
			);
			await e2eCall(
				request,
				'set_advance_settlement',
				{
					name: first.name,
					paid_amount: 10000,
					claimed_amount: 9200,
					status: 'Paid',
				},
				'admin',
			);

			const replenish = await e2eCall<{ ok: boolean }>(
				request,
				'try_create_advance',
				{ employee: emp, amount: 1500 },
				'employee',
			);
			expect(replenish.ok).toBe(true);
		});

		test('AC-ADV-007 @regression @critical: Settle advance via Expense Claim link', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);
			const advance = await e2eCall<{ name: string }>(
				request,
				'create_employee_advance',
				{ employee: emp, amount: 2000, submit: 1 },
				'employee',
			);
			await e2eCall(
				request,
				'workflow_action',
				{ doctype: 'Employee Advance', name: advance.name, action: 'Approve' },
				'manager',
			);
			await e2eCall(
				request,
				'set_advance_settlement',
				{
					name: advance.name,
					paid_amount: 2000,
					claimed_amount: 0,
					status: 'Paid',
				},
				'admin',
			);

			const claim = await e2eCall<{ name: string; workflow_state: string }>(
				request,
				'create_expense_claim',
				{ employee: emp, amount: 1500, submit: 1 },
				'employee',
			);
			expect(claim.workflow_state).toBe('Pending Approval');

			const hint = await callMethod<string>(
				request,
				'volunteering.volunteering.employee_advance_controls.get_linkable_advances_hint',
				{ employee: emp },
				'employee',
			);
			expect(hint.toLowerCase()).toMatch(/available|link/);
		});

		test('AC-ADV-008 @regression @critical: Get Advances hides unpaid advances', async ({
			request,
		}) => {
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			await cleanupEmployeeAdvances(request, emp);
			const draft = await e2eCall<{ name: string }>(
				request,
				'create_employee_advance',
				{ employee: emp, amount: 1000, submit: 0 },
				'employee',
			);
			expect(draft.name).toBeTruthy();

			const hint = await callMethod<string>(
				request,
				'volunteering.volunteering.employee_advance_controls.get_linkable_advances_hint',
				{ employee: emp },
				'employee',
			);
			expect(hint.toLowerCase()).toMatch(/not submitted|not paid|no advances qualify/);
		});
	});

	test('AC-ADV-004 @regression: Accounts can create advance for another', async ({
		request,
	}) => {
		const cast = await getCast(request, 'accounts');
		const emp = cast.employee.employee!;
		await cleanupEmployeeAdvances(request, emp);
		const advance = await e2eCall<{ name: string; workflow_state: string }>(
			request,
			'create_employee_advance',
			{ employee: emp, amount: 1500, submit: 1 },
			'accounts',
		);
		expect(advance.workflow_state).toBe('Pending Approval');
		const ownerEmp = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Employee Advance', name: advance.name, field: 'employee' },
			'admin',
		);
		expect(ownerEmp).toBe(emp);
	});

	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-ADV-010 @regression: Employee Advances with Residual report', async ({
			request,
		}) => {
			const report = await e2eCall<{ ok: boolean; columns?: unknown[] }>(
				request,
				'run_query_report',
				{ report_name: 'Employee Advances with Residual' },
				'accounts',
			);
			expect(report.ok).toBe(true);
			expect(report.columns).toBeTruthy();
		});
	});

	test.describe('as manager', () => {
		test.use({ storageState: personaStorage('manager') });

		test('AC-ADV-011 @regression: Manager self advance limit 5000', async ({ request }) => {
			const cast = await getCast(request, 'manager');
			const mgr = cast.manager.employee!;
			await cleanupEmployeeAdvances(request, mgr);
			const ok = await e2eCall<{ ok: boolean }>(
				request,
				'try_create_advance',
				{ employee: mgr, amount: 5000 },
				'manager',
			);
			expect(ok.ok).toBe(true);

			await cleanupEmployeeAdvances(request, mgr);
			const over = await e2eCall<{ ok: boolean; error?: string }>(
				request,
				'try_create_advance',
				{ employee: mgr, amount: 5001 },
				'manager',
			);
			expect(over.ok).toBe(false);
			expectErrorContains(over.error || '', 'limit');
		});
	});
});
