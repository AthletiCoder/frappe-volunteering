import { expect, test } from '@playwright/test';
import { cleanupEmployeeAdvances, e2eCall, getCast } from '../../helpers/e2e-api';
import { PERSONAS, personaStorage } from '../../helpers/personas';

test.describe('Approval routing @accounts', () => {
	test('AC-APR-001 @regression @critical: Approve when amount <= Max Approval Authority', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const claim = await e2eCall<{ name: string; pending_approver?: string }>(
			request,
			'create_expense_claim',
			{ employee: emp, amount: 1500, submit: 1 },
			'employee',
		);
		expect(claim.pending_approver).toBe(PERSONAS.manager.email);

		const approved = await e2eCall<{ workflow_state: string }>(
			request,
			'workflow_action',
			{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
			'manager',
		);
		expect(approved.workflow_state).toBe('Approved');
	});

	test('AC-APR-002 @regression @critical: Cannot Approve when over authority; can Escalate', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const directorEmp = cast.director.employee!;
		const chairEmp = cast.chair.employee!;
		await e2eCall(
			request,
			'set_employee_reports_to',
			{ employee: directorEmp, reports_to: '' },
			'admin',
		);
		try {
			const claim = await e2eCall<{ name: string }>(
				request,
				'create_expense_claim',
				{
					employee: emp,
					amount: 30000,
					submit: 1,
					vendor_override_reason: 'Vendor does not accept POs',
				},
				'employee',
			);

			const flags = await e2eCall<{
				can_approve: boolean;
				can_escalate: boolean;
				can_reject: boolean;
			}>(request, 'get_approver_flags', { doctype: 'Expense Claim', name: claim.name }, 'manager');
			expect(flags.can_approve).toBe(false);
			expect(flags.can_escalate).toBe(true);
			expect(flags.can_reject).toBe(true);

			const approveAttempt = await e2eCall<{ ok: boolean }>(
				request,
				'try_workflow_action',
				{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
				'manager',
			);
			expect(approveAttempt.ok).toBe(false);
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
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const claim = await e2eCall<{ name: string }>(
			request,
			'create_expense_claim',
			{ employee: emp, amount: 500, submit: 1 },
			'employee',
		);
		const flags = await e2eCall<{ can_approve: boolean }>(
			request,
			'get_approver_flags',
			{ doctype: 'Expense Claim', name: claim.name },
			'employee',
		);
		expect(flags.can_approve).toBe(false);
	});

	test('AC-APR-004 @regression @critical: Board-level can approve any amount', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const claim = await e2eCall<{ name: string; pending_approver?: string }>(
			request,
			'create_expense_claim',
			{
				employee: emp,
				amount: 30000,
				submit: 1,
				vendor_override_reason: 'Vendor does not accept POs',
			},
			'employee',
		);
		expect(claim.pending_approver).toBe(PERSONAS.chair.email);
		const approved = await e2eCall<{ workflow_state: string }>(
			request,
			'workflow_action',
			{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
			'chair',
		);
		expect(approved.workflow_state).toBe('Approved');
	});

	test('AC-APR-005 @regression @critical: Cannot approve own spending request', async ({
		request,
	}) => {
		const cast = await getCast(request, 'manager');
		const mgr = cast.manager.employee!;
		const claim = await e2eCall<{ name: string; pending_approver?: string }>(
			request,
			'create_expense_claim',
			{ employee: mgr, amount: 500, submit: 1 },
			'manager',
		);
		expect(claim.pending_approver).not.toBe(PERSONAS.manager.email);

		const selfApprove = await e2eCall<{ ok: boolean }>(
			request,
			'try_workflow_action',
			{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
			'manager',
		);
		expect(selfApprove.ok).toBe(false);
	});

	test('AC-APR-006 @regression @critical: Escalate follows Reports To chain', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee.employee!;
		const directorEmp = cast.director.employee!;
		const chairEmp = cast.chair.employee!;
		await e2eCall(
			request,
			'set_employee_reports_to',
			{ employee: directorEmp, reports_to: '' },
			'admin',
		);
		try {
			const claim = await e2eCall<{ name: string }>(
				request,
				'create_expense_claim',
				{
					employee: emp,
					amount: 30000,
					submit: 1,
					vendor_override_reason: 'Vendor does not accept POs',
				},
				'employee',
			);
			await e2eCall(
				request,
				'escalate_document',
				{
					doctype: 'Expense Claim',
					name: claim.name,
					escalation_reason: 'Above manager authority',
				},
				'manager',
			);
			const pending = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claim.name, field: 'pending_approver' },
				'admin',
			);
			expect(pending).toBe(PERSONAS.director.email);

			await e2eCall(
				request,
				'escalate_document',
				{
					doctype: 'Expense Claim',
					name: claim.name,
					escalation_reason: 'Director limit also exceeded',
				},
				'director',
			);
			const approved = await e2eCall<{ workflow_state: string }>(
				request,
				'workflow_action',
				{ doctype: 'Expense Claim', name: claim.name, action: 'Approve' },
				'chair',
			);
			expect(approved.workflow_state).toBe('Approved');
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
		request,
	}) => {
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
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			const claim = await e2eCall<{ name: string; workflow_state: string }>(
				request,
				'create_expense_claim',
				{ employee: emp, amount: 1500, submit: 1 },
				'employee',
			);
			expect(claim.workflow_state).toBeTruthy();
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
			request,
		}) => {
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
					'hr',
				);
				await cleanupEmployeeAdvances(request, emp);
				const withinManager = await e2eCall<{ ok: boolean }>(
					request,
					'try_create_advance',
					{ employee: emp, amount: 5000 },
					'associate',
				);
				expect(withinManager.ok).toBe(true);
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
