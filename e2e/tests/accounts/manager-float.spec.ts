import { expect, test } from '@playwright/test';
import { AdvancesPage } from '../../pages/advances.page';
import {
	cleanupEmployeeAdvances,
	cleanupExpenseClaimsForProject,
	e2eCall,
	getCast,
} from '../../helpers/e2e-api';
import {
	seedApproveExpenseClaim,
	seedEscalateExpenseClaim,
	seedManagerFloatClaim,
	setupManagerPaidAdvance,
} from '../../helpers/manager-float-fixtures';
import { PERSONAS, personaStorage } from '../../helpers/personas';
import { getE2eProject } from '../../helpers/ui-fixtures';
import { ExpenseClaimFormPage } from '../../pages/desk/expense-claim.page';

test.describe('Manager float reimbursement @accounts @ui', () => {
	// API fixtures use admin persona via fetch — default project storageState.
	test('AC-MFL-001 @regression @critical: Out of Pocket settles with the firm, not manager float', async ({
		request,
	}) => {
		test.setTimeout(120_000);
		const project = await getE2eProject(request);
		await cleanupExpenseClaimsForProject(request, project);

		const claim = await seedManagerFloatClaim(request, {
			amount: 1500,
			reimbursementSource: 'Out of Pocket',
		});
		expect(claim.reimbursement_source).toBe('Out of Pocket');

		const approved = await seedApproveExpenseClaim(request, claim.name, {
			budgetOverrideReason: 'E2E firm reimbursement approval.',
		});

		expect(approved.workflow_state).toBe('Approved');
		expect(approved.manager_float_advance || '').toBeFalsy();
		expect(Number(approved.total_amount_reimbursed || 0)).toBe(0);
	});

	test('AC-MFL-002 @regression @critical: Manager Advance approve settles from manager paid advance', async ({
		request,
	}) => {
		test.setTimeout(180_000);
		const cast = await getCast(request, 'employee');
		const mgrEmp = cast.manager.employee!;
		const project = await getE2eProject(request);
		await cleanupExpenseClaimsForProject(request, project);
		const advanceName = await setupManagerPaidAdvance(request, 5000);

		const claim = await seedManagerFloatClaim(request, {
			amount: 1500,
			reimbursementSource: 'Manager Advance',
		});
		expect(claim.manager_float_holder).toBe(mgrEmp);

		const approved = await seedApproveExpenseClaim(request, claim.name, {
			budgetOverrideReason: 'E2E manager float approval.',
		});

		const claimedAmount = await e2eCall<number>(
			request,
			'get_doc_field',
			{ doctype: 'Employee Advance', name: advanceName, field: 'claimed_amount' },
			'admin',
		);

		expect(approved.workflow_state).toBe('Approved');
		expect(approved.manager_float_advance).toBe(advanceName);
		expect(Number(approved.total_amount_reimbursed)).toBe(1500);
		expect(Number(claimedAmount)).toBe(1500);
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-MFL-004 @regression: Advance Portal shows manager float panel and out-of-pocket link', async ({
			page,
			request,
		}) => {
			await setupManagerPaidAdvance(request, 5000);

			const advances = new AdvancesPage(page);
			await advances.goto();
			await advances.expectLoaded();
			await expect(advances.managerFloatPanelHeading()).toBeVisible();
			await expect(advances.outOfPocketClaimLink()).toBeVisible();
			await expect(advances.managerFloatClaimLink()).toBeVisible();
			await expect(page.getByText(/Float available/i)).toBeVisible();
		});
	});

	test.describe('as manager', () => {
		test.use({ storageState: personaStorage('manager') });

		test('AC-MFL-003 @regression @critical: Manager without float blocks Approve and allows Escalate', async ({
			page,
			request,
		}) => {
			test.setTimeout(300_000);
			const cast = await getCast(request, 'manager');
			const mgrEmp = cast.manager.employee!;
			const project = await getE2eProject(request);
			await cleanupEmployeeAdvances(request, mgrEmp);
			await cleanupExpenseClaimsForProject(request, project);

			const claim = await seedManagerFloatClaim(request, {
				amount: 1200,
				reimbursementSource: 'Manager Advance',
			});

			const flags = await e2eCall<{
				can_approve: boolean;
				can_escalate: boolean;
				manager_float_blocked?: boolean;
			}>(
				request,
				'get_approver_flags',
				{ doctype: 'Expense Claim', name: claim.name },
				'manager',
			);
			expect(flags.can_approve).toBe(false);
			expect(flags.can_escalate).toBe(true);
			expect(flags.manager_float_blocked).toBe(true);

			const mgrClaim = new ExpenseClaimFormPage(page);
			await mgrClaim.open(claim.name);
			await mgrClaim.expectApproveNotVisible();

			const escalated = await seedEscalateExpenseClaim(
				request,
				claim.name,
				'Manager has no paid advance float.',
			);
			expect(escalated.pending_approver).toBe(PERSONAS.director.email);
			expect(escalated.workflow_state).toBe('Pending Approval');

			const pendingApprover = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claim.name, field: 'pending_approver' },
				'admin',
			);
			const workflowState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claim.name, field: 'workflow_state' },
				'admin',
			);
			expect(pendingApprover).toBe(PERSONAS.director.email);
			expect(workflowState).toBe('Pending Approval');
		});

		test('AC-MFL-005 @regression: Advance Portal lists pending team manager-float request', async ({
			page,
			request,
		}) => {
			test.setTimeout(180_000);
			const project = await getE2eProject(request);
			await setupManagerPaidAdvance(request, 5000);
			await cleanupExpenseClaimsForProject(request, project);

			const claim = await seedManagerFloatClaim(request, {
				amount: 900,
				reimbursementSource: 'Manager Advance',
			});

			const advances = new AdvancesPage(page);
			await advances.goto();
			await advances.expectLoaded();
			await advances.waitForTeamRequestsLoaded();
			await expect(advances.teamFloatRequestsHeading()).toBeVisible();
			await expect(advances.teamFloatRequestRow(claim.name)).toBeVisible();
			await expect(advances.teamFloatRequestStatus(claim.name)).toHaveText('Can fund');
		});
	});
});
