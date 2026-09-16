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

		test('AC-CLM-006 @regression @critical: New claim does not request Account permission', async ({
			page,
		}) => {
			const accountLinkValidations: string[] = [];
			page.on('request', (request) => {
				if (!request.url().includes('frappe.client.validate_link_and_fetch')) return;

				const url = new URL(request.url());
				if (url.searchParams.get('doctype') === 'Account') {
					accountLinkValidations.push(request.url());
				}
			});

			await page.goto(formUrl('Expense Claim'), {
				waitUntil: 'domcontentloaded',
			});
			await page.waitForFunction(
				() => {
					const frm = (
						window as unknown as {
							cur_frm?: {
								doctype?: string;
								doc?: { employee?: string; company?: string };
							};
						}
					).cur_frm;
					return frm?.doctype === 'Expense Claim' && Boolean(frm.doc?.employee && frm.doc?.company);
				},
				undefined,
				{ timeout: 45000 },
			);
			await page.waitForTimeout(1000);
			const payableField = await page.evaluate(() => {
				const field = (
					window as unknown as {
						cur_frm?: {
							fields_dict?: {
								payable_account?: {
									df?: {
										reqd?: number;
										fetch_from?: string;
										mandatory_depends_on?: string;
									};
								};
							};
						};
					}
				).cur_frm?.fields_dict?.payable_account?.df;
				return {
					reqd: Number(field?.reqd || 0),
					fetch_from: field?.fetch_from || '',
					mandatory_depends_on: field?.mandatory_depends_on || '',
				};
			});

			await expect(
				page.locator('.modal.show').filter({ hasText: /Insufficient Permission for Account/i }),
			).toHaveCount(0);
			expect(payableField).toEqual({
				reqd: 0,
				fetch_from: '',
				mandatory_depends_on: '',
			});
			expect(accountLinkValidations).toEqual([]);
		});

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
				expenseAccount: masters.expense_account,
			});
			claimName = await claim.saveAndSubmit(request, { reviewReceipts: false });

			const reviewState = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
				'admin',
			);
			expect(reviewState).toBe('Pending Receipt Review');

			await withPersona(browser, 'receipt_reviewer', async (reviewerPage) => {
				const reviewerClaim = new ExpenseClaimFormPage(reviewerPage);
				await reviewerClaim.open(claimName);
				await reviewerClaim.verifyReceipts();
			});

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
						expenseAccount: masters.expense_account,
					});
					await first.saveAndSubmit(request);

					const second = new ExpenseClaimFormPage(empPage);
					await second.openNew();
					await second.fillClaim({
						project,
						amount: 1000,
						expenseAccount: masters.expense_account,
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

		test('AC-CLM-003 @regression: Monthly Reimbursement Cap 0 = unlimited', async ({ request, browser }) => {
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
					expenseAccount: masters.expense_account,
				});
				await first.saveAndSubmit(request);

				const second = new ExpenseClaimFormPage(page);
				await second.openNew();
				await second.fillClaim({
					project,
					amount: 1500,
					expenseAccount: masters.expense_account,
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

		test('AC-CLM-005 @regression: Claim requires receipts before submit', async ({ page, request }) => {
			const project = await getE2eProject(request);
			const masters = await getE2eMasters(request);

			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 1200,
				expenseAccount: masters.expense_account,
			});
			const draftName = await claim.saveDraft();
			await claim.submitExpectValidationError(draftName);
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
				expenseAccount: masters.expense_account,
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
			const claim = new ExpenseClaimFormPage(page);
			await claim.open(claimName);
			await expect(page.getByText(/^Rejected$/i).first()).toBeVisible();
			// Accounts may view rejected claims; Approve must not stay available.
			await claim.expectApproveNotVisible();
		});
	});
});
