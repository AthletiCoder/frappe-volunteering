import { expect, test } from '@playwright/test';
import { e2eCall, cleanupExpenseClaimsForProject, getCast } from '../../helpers/e2e-api';
import { expectFormError } from '../../helpers/dialogs';
import { formUrl } from '../../helpers/desk';
import { withPersona } from '../../helpers/persona-context';
import { personaStorage } from '../../helpers/personas';
import { getE2eMasters, getE2eProject } from '../../helpers/ui-fixtures';
import { ExpenseClaimFormPage } from '../../pages/desk/expense-claim.page';

test.describe('Expense Claim @accounts @ui', () => {
	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-CLM-001 @regression @critical: Reimbursement happy path to Approved', async ({
			page,
			request,
			browser,
		}) => {
			test.setTimeout(240_000);
			const project = await getE2eProject(request);
			await cleanupExpenseClaimsForProject(request, project);
			const masters = await getE2eMasters(request);

			let claimName = '';
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 1500,
				expenseType: masters.expense_type,
			});
			claimName = await claim.saveAndSubmit(request);

			const workflowState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
				'admin',
			);
			expect(workflowState).toBe('Pending Approval');

			await withPersona(browser, 'manager', async (mgrPage) => {
				const mgrClaim = new ExpenseClaimFormPage(mgrPage);
				await mgrClaim.open(claimName);
				await mgrClaim.approve({
					budgetOverrideReason: 'E2E approval within department plan.',
				});
			});

			const approvedState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
				'admin',
			);
			const docstatus = await e2eCall<number>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claimName, field: 'docstatus' },
				'admin',
			);
			expect(approvedState).toBe('Approved');
			expect(docstatus).toBe(1);
		});

		test('AC-CLM-002 @regression @critical: Monthly Reimbursement Cap blocks excess', async ({
			request,
			browser,
		}) => {
			test.setTimeout(300_000);
			const cast = await getCast(request, 'employee_b');
			const emp = cast.employee_b.employee!;
			const project = await getE2eProject(request);
			const masters = await getE2eMasters(request);
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
				await withPersona(browser, 'employee_b', async (empPage) => {
					const first = new ExpenseClaimFormPage(empPage);
					await first.openNew();
					await first.fillClaim({
						project,
						amount: 2500,
						expenseType: masters.expense_type,
					});
					await first.saveAndSubmit(request);

					const second = new ExpenseClaimFormPage(empPage);
					await second.openNew();
					await second.fillClaim({
						project,
						amount: 1000,
						expenseType: masters.expense_type,
					});
					await second.save({ expectError: /cap|exceed/i });
				});
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
			browser,
		}) => {
			test.setTimeout(300_000);
			const project = await getE2eProject(request);
			const masters = await getE2eMasters(request);
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

			let secondName = '';
			await withPersona(browser, 'associate', async (page) => {
				const first = new ExpenseClaimFormPage(page);
				await first.openNew();
				await first.fillClaim({
					project,
					amount: 1500,
					expenseType: masters.expense_type,
				});
				await first.saveAndSubmit(request);

				const second = new ExpenseClaimFormPage(page);
				await second.openNew();
				await second.fillClaim({
					project,
					amount: 1500,
					expenseType: masters.expense_type,
				});
				secondName = await second.saveAndSubmit(request);
			});

			const workflowState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: secondName, field: 'workflow_state' },
				'admin',
			);
			expect(workflowState).toBe('Pending Approval');
		});

		test('AC-CLM-005 @regression: Claim requires receipts before submit', async ({
			page,
			request,
		}) => {
			const project = await getE2eProject(request);
			const masters = await getE2eMasters(request);

			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 1200,
				expenseType: masters.expense_type,
			});
			const draftName = await claim.saveDraft();
			await claim.submit();
			await expectFormError(page, /receipt|attach/i);
			expect(draftName).toBeTruthy();
		});
	});

	test('AC-CLM-004 @regression: Reject expense claim', async ({ browser, request }) => {
		test.setTimeout(240_000);
		const project = await getE2eProject(request);
		const masters = await getE2eMasters(request);

		let claimName = '';
		await withPersona(browser, 'employee', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 1200,
				expenseType: masters.expense_type,
			});
			claimName = await claim.saveAndSubmit(request);
		});

		await withPersona(browser, 'manager', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			await claim.reject();
		});

		const workflowState = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
			'admin',
		);
		expect(workflowState).toBe('Rejected');

		await withPersona(browser, 'accounts', async (page) => {
			await page.goto(formUrl('Expense Claim', claimName), { waitUntil: 'domcontentloaded' });
			await expectFormError(page, /not permitted|reject|cannot|permission/i);
		});
	});
});
