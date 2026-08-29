import { expect, type APIRequestContext, type Page } from '@playwright/test';
import { modal } from '../../helpers/dialogs';
import { DeskForm, formUrl } from '../../helpers/desk';
import { attachClaimReceipt } from '../../helpers/ui-fixtures';

export class ExpenseClaimFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Expense Claim');
		await this.dismissFormOverlays();
		await this.dismissBlockingModals();
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { cur_frm?: { doc?: unknown } }).cur_frm?.doc),
			undefined,
			{ timeout: 45000 },
		);
		await this.ensureSelfEmployee();
	}

	async open(name: string): Promise<void> {
		await this.page.goto(formUrl('Expense Claim', name), { waitUntil: 'domcontentloaded' });
		await this.page.waitForFunction(
			(expected) =>
				(window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc?.name ===
				expected,
			name,
			{ timeout: 45000 },
		);
		await this.dismissBlockingModals();
	}

	async ensureSelfEmployee(): Promise<void> {
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { cur_frm?: { doc?: unknown } }).cur_frm?.doc),
			undefined,
			{ timeout: 45000 },
		);
		await this.page.evaluate(async () => {
			const win = window as unknown as {
				cur_frm?: {
					doc?: { employee?: string; expense_approver?: string; currency?: string };
					set_value: (f: string, v: string) => Promise<unknown>;
					trigger?: (e: string) => void;
				};
				frappe?: {
					session: { user: string };
					db: {
						get_value: (
							dt: string,
							f: Record<string, string> | string,
							field: string | string[],
						) => Promise<{ message?: Record<string, string> & { name?: string } }>;
					};
					xcall: (method: string, args: Record<string, string>) => Promise<string | null>;
				};
			};
			const frm = win.cur_frm;
			if (!frm || !win.frappe) {
				return;
			}
			if (!frm.doc?.employee) {
				const user = win.frappe.session.user;
				const res = await win.frappe.db.get_value('Employee', { user_id: user }, 'name');
				const name = res?.message?.name;
				if (name) {
					await frm.set_value('employee', name);
				}
			}
			frm.trigger?.('employee');
			if (frm.doc?.employee) {
				const empRes = await win.frappe.db.get_value('Employee', frm.doc.employee, [
					'company',
					'department',
				]);
				const employeeMeta = empRes?.message || {};
				if (!frm.doc?.company && employeeMeta.company) {
					await frm.set_value('company', employeeMeta.company);
				}
				if (!frm.doc?.department && employeeMeta.department) {
					await frm.set_value('department', employeeMeta.department);
				}
			}
			if (!frm.doc?.expense_approver && frm.doc?.employee) {
				const approver = await win.frappe.xcall(
					'volunteering.volunteering.approval_routing.get_expense_approver_for_employee',
					{ employee: frm.doc.employee },
				);
				if (approver) {
					await frm.set_value('expense_approver', approver);
				}
			}
			if (!frm.doc?.currency && frm.doc?.company) {
				const currencyRes = await win.frappe.db.get_value(
					'Company',
					frm.doc.company,
					'default_currency',
				);
				const currency =
					typeof currencyRes?.message === 'string'
						? currencyRes.message
						: currencyRes?.message?.default_currency;
				await frm.set_value('currency', currency || 'INR');
			}
			if (!frm.doc?.exchange_rate) {
				await frm.set_value('exchange_rate', 1);
			}
			if (!frm.doc?.payable_account && frm.doc?.company) {
				const payableRes = await win.frappe.db.get_value(
					'Company',
					frm.doc.company,
					'default_expense_claim_payable_account',
				);
				let payable =
					typeof payableRes?.message === 'string'
						? payableRes.message
						: payableRes?.message?.default_expense_claim_payable_account;
				if (!payable) {
					const fallback = await win.frappe.db.get_value(
						'Company',
						frm.doc.company,
						'default_payable_account',
					);
					payable =
						typeof fallback?.message === 'string'
							? fallback.message
							: fallback?.message?.default_payable_account;
				}
				if (payable) {
					await frm.set_value('payable_account', payable);
				}
			}
			if (!frm.doc?.posting_date) {
				await frm.set_value('posting_date', win.frappe.datetime.get_today());
			}
		});
		await this.page.waitForFunction(
			() => {
				const doc = (window as unknown as {
					cur_frm?: {
						doc?: {
							currency?: string;
							expense_approver?: string;
							employee?: string;
							company?: string;
							exchange_rate?: number;
							payable_account?: string;
						};
					};
				}).cur_frm?.doc;
				return Boolean(
					doc?.employee &&
						doc?.currency &&
						doc?.expense_approver &&
						doc?.company &&
						doc?.exchange_rate &&
						doc?.payable_account,
				);
			},
			undefined,
			{ timeout: 45000 },
		);
	}

	private async setExpenseRow(expenseType: string, amount: number): Promise<void> {
		await this.page.evaluate(
			async ({ expenseType: type, amount: amt }) => {
				const win = window as unknown as {
					cur_frm?: {
						clear_table: (table: string) => void;
						add_child: (table: string) => { doctype: string; name: string };
						refresh_field: (table: string) => void;
					};
					frappe?: {
						model: {
							set_value: (
								dt: string,
								name: string,
								field: string,
								val: string | number,
							) => Promise<void>;
						};
					};
				};
				const frm = win.cur_frm;
				if (!frm || !win.frappe?.model) {
					return;
				}
				frm.clear_table('expenses');
				const row = frm.add_child('expenses');
				await win.frappe.model.set_value(row.doctype, row.name, 'expense_type', type);
				await win.frappe.model.set_value(row.doctype, row.name, 'amount', amt);
				await win.frappe.model.set_value(row.doctype, row.name, 'sanctioned_amount', amt);
				frm.refresh_field('expenses');
			},
			{ expenseType, amount },
		);
		await this.page.waitForFunction(
			({ type, amt }) => {
				const expenses =
					(window as unknown as { cur_frm?: { doc?: { expenses?: Array<{ expense_type?: string; amount?: number }> } } })
						.cur_frm?.doc?.expenses || [];
				return expenses.some((row) => row.expense_type === type && Number(row.amount) === amt);
			},
			{ type: expenseType, amt: amount },
			{ timeout: 10000 },
		);
	}

	private async setProject(project: string): Promise<void> {
		await this.page.evaluate(async (proj) => {
			const win = window as unknown as {
				cur_frm?: {
					doc?: { expenses?: Array<{ doctype: string; name: string }> };
					set_value: (f: string, v: string) => Promise<unknown>;
				};
				frappe?: {
					db: { get_value: (dt: string, name: string, field: string) => Promise<{ message?: { cost_center?: string } }> };
					model: {
						set_value: (dt: string, name: string, field: string, val: string) => Promise<void>;
					};
				};
			};
			const frm = win.cur_frm;
			if (!frm) {
				return;
			}
			await frm.set_value('project', proj);
			const ccRes = await win.frappe?.db.get_value('Project', proj, 'cost_center');
			const costCenter =
				typeof ccRes?.message === 'string' ? ccRes.message : ccRes?.message?.cost_center;
			if (costCenter) {
				await frm.set_value('cost_center', costCenter);
				for (const row of frm.doc?.expenses || []) {
					await win.frappe?.model.set_value(row.doctype, row.name, 'cost_center', costCenter);
				}
			}
		}, project);
		await this.page.waitForFunction(
			(proj) =>
				(window as unknown as { cur_frm?: { doc?: { project?: string } } }).cur_frm?.doc?.project ===
				proj,
			project,
			{ timeout: 10000 },
		);
	}

	async setReimbursementSource(source: 'Out of Pocket' | 'Manager Advance'): Promise<void> {
		await this.clickTab('Approval & Routing');
		await this.page.evaluate(async (value) => {
			const frm = (window as unknown as {
				cur_frm?: { set_value: (field: string, val: string) => Promise<unknown> };
			}).cur_frm;
			if (frm) {
				await frm.set_value('reimbursement_source', value);
			}
		}, source);
		await this.page.waitForFunction(
			(expected) =>
				(window as unknown as { cur_frm?: { doc?: { reimbursement_source?: string } } }).cur_frm?.doc
					?.reimbursement_source === expected,
			source,
			{ timeout: 10000 },
		);
	}

	async fillClaim(options: {
		project: string;
		amount: number;
		expenseType?: string;
		vendorOverrideReason?: string;
		budgetOverrideReason?: string;
		reimbursementSource?: 'Out of Pocket' | 'Manager Advance';
	}): Promise<void> {
		await this.ensureSelfEmployee();
		await this.clickTab('Expenses & Advances');
		const expenseType = options.expenseType || '_Test Accounting Expense';
		await this.setExpenseRow(expenseType, options.amount);

		await this.setProject(options.project);
		await this.dismissFormOverlays();
		await this.clickTab('Expenses & Advances');
		if (options.vendorOverrideReason || options.budgetOverrideReason || options.reimbursementSource) {
			await this.clickTab('Approval & Routing');
		}
		if (options.reimbursementSource) {
			await this.setReimbursementSource(options.reimbursementSource);
		}
		if (options.vendorOverrideReason) {
			await this.fillData('vendor_override_reason', options.vendorOverrideReason);
		}
		if (options.budgetOverrideReason) {
			await this.fillData('budget_override_reason', options.budgetOverrideReason);
		}
		if (options.vendorOverrideReason || options.budgetOverrideReason || options.reimbursementSource) {
			await this.clickTab('Expenses & Advances');
		}
	}

	async saveDraft(): Promise<string> {
		await this.save();
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Expense Claim name not found after save');
		}
		return name;
	}

	async saveExpectVendorWarning(): Promise<void> {
		await this.save({ expectWarning: /vendor|threshold|Prefer/i });
	}

	async saveAndSubmit(
		request: APIRequestContext,
		options?: { expectBudgetWarning?: boolean; attachReceipt?: boolean },
	): Promise<string> {
		const name = await this.saveDraft();
		if (options?.attachReceipt !== false) {
			await attachClaimReceipt(request, name);
		}
		if (options?.expectBudgetWarning) {
			await this.submit({ expectWarning: /budget|exceed/i, allowConfirm: true });
		} else {
			await this.submit({ allowConfirm: true });
		}
		return name;
	}

	async approve(options?: { budgetOverrideReason?: string }): Promise<void> {
		if (options?.budgetOverrideReason) {
			await this.page.evaluate(async (reason) => {
				const frm = (window as unknown as {
					cur_frm?: { set_value: (f: string, v: string) => Promise<unknown>; save?: () => Promise<void> };
				}).cur_frm;
				if (frm) {
					await frm.set_value('budget_override_reason', reason);
					await frm.save?.();
				}
			}, options.budgetOverrideReason);
			await this.page.waitForTimeout(800);
		}
		await this.dismissBlockingModals();
		await this.page
			.waitForFunction(
				() => {
					const btn = document.querySelector('.page-head .primary-action');
					return Boolean(btn && !btn.classList.contains('hide') && btn.textContent?.includes('Approve'));
				},
				undefined,
				{ timeout: 30000 },
			)
			.catch(() => {});
		await this.clickWorkflowAction('Approve', { allowConfirm: true });
		await this.page
			.locator('.indicator-pill, .form-docstatus')
			.filter({ hasText: /Approved/i })
			.first()
			.waitFor({ state: 'visible', timeout: 30000 });
	}

	async reject(): Promise<void> {
		await this.clickWorkflowAction('Reject');
	}

	async escalate(reason = 'E2E escalation'): Promise<void> {
		const reviewBtn = this.page.locator('.inner-group-button, button').filter({ hasText: /^Review$/ }).first();
		if (await reviewBtn.isVisible().catch(() => false)) {
			await reviewBtn.click();
		}
		const escalateBtn = this.page.locator('.dropdown-item, button').filter({ hasText: 'Escalate' }).first();
		await escalateBtn.click();
		const dialog = modal(this.page);
		await dialog.locator('[data-fieldname="escalation_reason"] textarea, input').fill(reason);
		await dialog.getByRole('button', { name: /Submit|OK/i }).click();
		await this.page.waitForTimeout(800);
	}

	async expectApproveNotVisible(): Promise<void> {
		const primaryApprove = this.page.locator('.page-head .primary-action').filter({ hasText: /^Approve$/ });
		await expect(primaryApprove).toHaveCount(0);
	}

	async expectEscalateVisible(): Promise<void> {
		await this.page
			.waitForFunction(
				() => {
					const labels = Array.from(document.querySelectorAll('.custom-btn, .btn, .dropdown-item'))
						.map((el) => el.textContent?.trim() || '');
					return labels.some((text) => text === 'Review' || text === 'Escalate');
				},
				undefined,
				{ timeout: 30000 },
			)
			.catch(() => {});
		const reviewBtn = this.page.locator('.inner-group-button, button, .custom-btn').filter({ hasText: /^Review$/ }).first();
		if (await reviewBtn.isVisible().catch(() => false)) {
			await reviewBtn.click();
		}
		const escalateBtn = this.page.locator('.dropdown-item, button, .custom-btn').filter({ hasText: 'Escalate' }).first();
		await escalateBtn.waitFor({ state: 'visible', timeout: 15000 });
	}
}
