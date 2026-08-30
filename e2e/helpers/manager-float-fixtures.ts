import type { APIRequestContext } from '@playwright/test';
import { cleanupEmployeeAdvances, e2eCall, getCast } from './e2e-api';

export interface SeededExpenseClaim {
	name: string;
	workflow_state?: string;
	reimbursement_source?: string;
	manager_float_holder?: string;
}

export interface SeededWorkflowResult {
	name: string;
	workflow_state?: string;
	manager_float_advance?: string | null;
	total_amount_reimbursed?: number;
}

/** Submitted + paid manager advance for manager-float E2E (fixture API, not a UI action). */
export async function setupManagerPaidAdvance(
	request: APIRequestContext,
	paidAmount = 5000,
): Promise<string> {
	const cast = await getCast(request, 'manager');
	const mgrEmp = cast.manager.employee!;
	await cleanupEmployeeAdvances(request, mgrEmp);
	const created = await e2eCall<{ name: string }>(
		request,
		'seed_manager_paid_advance',
		{ employee: mgrEmp, paid_amount: paidAmount },
		'admin',
	);
	return created.name;
}

export async function seedManagerFloatClaim(
	request: APIRequestContext,
	options?: {
		amount?: number;
		reimbursementSource?: 'Out of Pocket' | 'Manager Advance';
		employee?: string;
	},
): Promise<SeededExpenseClaim> {
	const cast = await getCast(request, 'employee');
	const employee = options?.employee || cast.employee.employee!;
	return e2eCall<SeededExpenseClaim>(
		request,
		'seed_expense_claim',
		{
			employee,
			amount: options?.amount ?? 1500,
			reimbursement_source: options?.reimbursementSource ?? 'Out of Pocket',
			submit: 1,
		},
		'admin',
	);
}

export async function seedApproveExpenseClaim(
	request: APIRequestContext,
	claimName: string,
	options?: { budgetOverrideReason?: string },
): Promise<SeededWorkflowResult> {
	return e2eCall<SeededWorkflowResult>(
		request,
		'seed_workflow_action',
		{
			doctype: 'Expense Claim',
			name: claimName,
			action: 'Approve',
			budget_override_reason: options?.budgetOverrideReason,
		},
		'admin',
	);
}

export async function seedEscalateExpenseClaim(
	request: APIRequestContext,
	claimName: string,
	escalationReason: string,
): Promise<{ name: string; workflow_state?: string; pending_approver?: string }> {
	return e2eCall(
		request,
		'seed_escalate_document',
		{
			doctype: 'Expense Claim',
			name: claimName,
			escalation_reason: escalationReason,
		},
		'admin',
	);
}
