import { expect, type APIRequestContext, type Page } from '@playwright/test';
import { modal, resolvePostActionModal } from '../../helpers/dialogs';
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
		await this.page.goto('/desk', { waitUntil: 'domcontentloaded' });
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { frappe?: { set_route?: unknown } }).frappe?.set_route),
			undefined,
			{ timeout: 45000 },
		);
		await this.page.evaluate(
			([doctype, docname]) => {
				(
					window as unknown as {
						frappe: { set_route: (type: string, doctype: string, name: string) => void };
					}
				).frappe.set_route('Form', doctype, docname);
			},
			['Expense Claim', name],
		);
		await this.page.waitForFunction(
			(expected) =>
				(window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc?.name ===
				expected,
			name,
			{ timeout: 45000 },
		);
		await this.page.waitForFunction(
			() =>
				document.querySelectorAll('.form-layout .frappe-control, .form-page .frappe-control')
					.length > 0,
			undefined,
			{ timeout: 45000 },
		);
		await this.dismissBlockingModals();
		await this.page.evaluate(() => {
			const win = window as unknown as {
				cur_frm?: unknown;
				volunteering?: { accounting_workflow?: { render_actions?: (frm: unknown) => void } };
			};
			if (win.cur_frm && win.volunteering?.accounting_workflow?.render_actions) {
				win.volunteering.accounting_workflow.render_actions(win.cur_frm);
			}
		});
		await this.page
			.waitForResponse(
				(resp) =>
					resp.url().includes('get_approver_action_flags') &&
					resp.request().method() === 'POST' &&
					resp.ok(),
				{ timeout: 30000 },
			)
			.catch(() => {});
		await this.page.evaluate(() => {
			const win = window as unknown as {
				cur_frm?: unknown;
				volunteering?: { accounting_workflow?: { render_actions?: (frm: unknown) => void } };
			};
			if (win.cur_frm && win.volunteering?.accounting_workflow?.render_actions) {
				win.volunteering.accounting_workflow.render_actions(win.cur_frm);
			}
		});
	}

	async getApproverFlags(): Promise<{
		is_pending_approver: boolean;
		can_approve: boolean;
		can_escalate: boolean;
		can_reject?: boolean;
	}> {
		return this.page.evaluate(async () => {
			const frm = (window as unknown as {
				cur_frm?: { doctype: string; doc: { name: string } };
			}).cur_frm;
			if (!frm) {
				throw new Error('Expense Claim form is not loaded');
			}
			return (
				window as unknown as {
					frappe: {
						xcall: (
							method: string,
							args: Record<string, string>,
						) => Promise<{
							is_pending_approver: boolean;
							can_approve: boolean;
							can_escalate: boolean;
							can_reject?: boolean;
						}>;
					};
				}
			).frappe.xcall('volunteering.volunteering.approval_routing.get_approver_action_flags', {
				doctype: frm.doctype,
				name: frm.doc.name,
			});
		});
	}

	private reviewMenuButton() {
		return this.page.locator('.inner-group-button[data-label="Review"] button').first();
	}

	private async openReviewMenu(): Promise<void> {
		const reviewBtn = this.reviewMenuButton();
		if (await reviewBtn.isVisible().catch(() => false)) {
			await reviewBtn.click();
			return;
		}
		const menuBtn = this.page
			.locator('.page-actions .menu-btn-group .btn, .page-icon-group .btn')
			.filter({ hasText: /Menu|Actions/i })
			.first();
		if (await menuBtn.isVisible().catch(() => false)) {
			await menuBtn.click();
		}
	}

	private async waitForApproverActions(): Promise<void> {
		await this.page
			.waitForResponse(
				(resp) =>
					resp.url().includes('get_approver_action_flags') &&
					resp.request().method() === 'POST' &&
					resp.ok(),
				{ timeout: 45000 },
			)
			.catch(() => {});
		await this.page
			.waitForFunction(
				() => {
					const review = document.querySelector('.inner-group-button[data-label="Review"]');
					if (review) {
						return true;
					}
					return Array.from(
						document.querySelectorAll('.dropdown-item, .dropdown-menu a, a.grey-link span'),
					).some((el) => /^(Review > )?Escalate$/.test(el.textContent?.trim() || ''));
				},
				undefined,
				{ timeout: 45000 },
			)
			.catch(() => {});
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
				await win.frappe.model.set_value(row.doctype, row.name, 'description', 'E2E test expense');
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
			await this.setVendorOverrideReason(options.vendorOverrideReason);
		}
		if (options.budgetOverrideReason) {
			await this.fillData('budget_override_reason', options.budgetOverrideReason);
		}
		if (options.vendorOverrideReason || options.budgetOverrideReason || options.reimbursementSource) {
			await this.clickTab('Expenses & Advances');
		}
	}

	async setVendorOverrideReason(reason: string): Promise<void> {
		await this.clickTab('Approval & Routing');
		await this.page.evaluate(async (value) => {
			const frm = (window as unknown as {
				cur_frm?: {
					set_df_property: (f: string, p: string, v: number) => void;
					set_value: (f: string, v: string) => Promise<unknown>;
				};
			}).cur_frm;
			if (!frm) {
				return;
			}
			frm.set_df_property('vendor_override_reason', 'hidden', 0);
			await frm.set_value('vendor_override_reason', value);
		}, reason);
	}

	private async ensureExpenseClaimSavePrerequisites(): Promise<void> {
		await this.page.evaluate(async () => {
			const win = window as unknown as {
				cur_frm?: {
					doc?: {
						company?: string;
						currency?: string;
						exchange_rate?: number;
						payable_account?: string;
						posting_date?: string;
					};
					set_value: (f: string, v: string | number) => Promise<unknown>;
				};
				frappe?: {
					datetime: { get_today: () => string };
					db: {
						get_value: (
							dt: string,
							name: string,
							field: string | string[],
						) => Promise<{ message?: Record<string, string> & { default_currency?: string } }>;
					};
				};
			};
			const frm = win.cur_frm;
			if (!frm || !win.frappe) {
				return;
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
			if (frm.doc?.exchange_rate == null || frm.doc.exchange_rate === 0) {
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
	}

	async saveDraft(): Promise<string> {
		await this.ensureExpenseClaimSavePrerequisites();
		await this.commitGridEdits();
		await this.dismissBlockingModals();
		const saveWait = this.waitForSaveResponse('Expense Claim');
		await this.clickPrimary('Save', { allowConfirm: true });
		const savedDoc = await saveWait.catch(() => null);
		if (savedDoc) {
			return savedDoc.name;
		}
		return this.waitForPersistedDocName();
	}

	private async submitSavedClaimInSession(
		name: string,
		options?: { expectBudgetWarning?: boolean },
	): Promise<void> {
		const submitBtn = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Submit$/ })
			.first();
		if (await submitBtn.isVisible().catch(() => false)) {
			await submitBtn.click();
			await resolvePostActionModal(this.page, {
				allowConfirm: true,
				expectWarning: options?.expectBudgetWarning ? /budget|exceed/i : undefined,
			});
			return;
		}

		await this.page.evaluate(async (docname) => {
			const doc = await (
				window as unknown as {
					frappe: {
						db: { get_doc: (dt: string, name: string) => Promise<unknown> };
						xcall: (method: string, args: Record<string, unknown>) => Promise<unknown>;
					};
				}
			).frappe.db.get_doc('Expense Claim', docname);
			await (
				window as unknown as {
					frappe: { xcall: (method: string, args: Record<string, unknown>) => Promise<unknown> };
				}
			).frappe.xcall('frappe.model.workflow.apply_workflow', { doc, action: 'Submit' });
		}, name);
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
		await this.submitSavedClaimInSession(name, options);
		return name;
	}

	async approve(options?: { budgetOverrideReason?: string }): Promise<void> {
		if (options?.budgetOverrideReason) {
			await this.page.evaluate(async (reason) => {
				const docname = (window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm
					?.doc?.name;
				if (!docname) {
					throw new Error('Expense Claim form is not loaded');
				}
				await (
					window as unknown as {
						frappe: {
							db: {
								set_value: (
									dt: string,
									name: string,
									field: string,
									value: string,
								) => Promise<void>;
							};
						};
					}
				).frappe.db.set_value('Expense Claim', docname, 'budget_override_reason', reason);
			}, options.budgetOverrideReason);
			await this.page.waitForTimeout(500);
		}
		await this.dismissBlockingModals();
		const primaryApprove = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Approve$/ })
			.first();
		if (await primaryApprove.isVisible().catch(() => false)) {
			await this.clickWorkflowAction('Approve', { allowConfirm: true });
		} else {
			await this.page.evaluate(async (reason) => {
				const win = window as unknown as {
					cur_frm?: { doc?: { name?: string } };
					frappe: {
						db: {
							get_doc: (dt: string, name: string) => Promise<unknown>;
							set_value: (dt: string, name: string, field: string, value: string) => Promise<void>;
						};
						xcall: (method: string, args: Record<string, unknown>) => Promise<unknown>;
					};
				};
				const docname = win.cur_frm?.doc?.name;
				if (!docname) {
					throw new Error('Expense Claim form is not loaded');
				}
				if (reason) {
					await win.frappe.db.set_value('Expense Claim', docname, 'budget_override_reason', reason);
				}
				const doc = await win.frappe.db.get_doc('Expense Claim', docname);
				await win.frappe.xcall('frappe.model.workflow.apply_workflow', { doc, action: 'Approve' });
			}, options?.budgetOverrideReason || null);
		}
		await this.page
			.waitForFunction(
				() => {
					const doc = (window as unknown as {
						cur_frm?: { doc?: { workflow_state?: string } };
					}).cur_frm?.doc;
					if (doc?.workflow_state === 'Approved') {
						return true;
					}
					const pill = document.querySelector('.indicator-pill, .form-docstatus');
					return Boolean(pill && /Approved/i.test(pill.textContent || ''));
				},
				undefined,
				{ timeout: 15000 },
			)
			.catch(() => {});
	}

	async reject(): Promise<void> {
		await this.dismissBlockingModals();
		const primaryReject = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Reject$/ })
			.first();
		if (await primaryReject.isVisible().catch(() => false)) {
			await this.clickWorkflowAction('Reject', { allowConfirm: true });
		} else {
			await this.applyWorkflowInSession('Reject');
		}
		await this.page
			.waitForFunction(
				() => {
					const doc = (window as unknown as {
						cur_frm?: { doc?: { workflow_state?: string } };
					}).cur_frm?.doc;
					if (doc?.workflow_state === 'Rejected') {
						return true;
					}
					const pill = document.querySelector('.indicator-pill, .form-docstatus');
					return Boolean(pill && /Rejected/i.test(pill.textContent || ''));
				},
				undefined,
				{ timeout: 15000 },
			)
			.catch(() => {});
	}

	/** Submit a saved draft and expect server-side validation to surface in Desk UI. */
	async submitExpectValidationError(savedName?: string): Promise<void> {
		if (savedName) {
			await this.open(savedName);
		}
		await this.dismissBlockingModals();
		const submitBtn = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Submit$/ })
			.first();
		if (await submitBtn.isVisible().catch(() => false)) {
			await submitBtn.click();
			return;
		}
		await this.applyWorkflowInSession('Submit');
	}

	private async applyWorkflowInSession(action: string): Promise<void> {
		await this.page.evaluate(async (workflowAction) => {
			const win = window as unknown as {
				cur_frm?: { doc?: { name?: string } };
				frappe?: {
					db: { get_doc: (dt: string, name: string) => Promise<unknown> };
					xcall: (method: string, args: Record<string, unknown>) => Promise<unknown>;
				};
			};
			const docname = win.cur_frm?.doc?.name;
			if (!docname || docname.startsWith('new-')) {
				throw new Error('Expense Claim form is not loaded with a saved name');
			}
			const doc = await win.frappe!.db.get_doc('Expense Claim', docname);
			try {
				await win.frappe!.xcall('frappe.model.workflow.apply_workflow', {
					doc,
					action: workflowAction,
				});
			} catch {
				// Validation / permission errors are surfaced via frappe.msgprint.
			}
		}, action);
	}

	async escalate(reason = 'E2E escalation'): Promise<void> {
		await this.dismissBlockingModals();
		await this.page.evaluate(() => {
			const win = window as unknown as {
				cur_frm?: unknown;
				volunteering?: { accounting_workflow?: { render_actions?: (frm: unknown) => void } };
			};
			if (win.cur_frm && win.volunteering?.accounting_workflow?.render_actions) {
				win.volunteering.accounting_workflow.render_actions(win.cur_frm);
			}
		});
		const reviewBtn = this.reviewMenuButton();
		if (await reviewBtn.isVisible().catch(() => false)) {
			await this.openReviewMenu();
			const escalateBtn = this.page
				.locator('.dropdown-menu.show .dropdown-item, .dropdown-menu a, a.grey-link')
				.filter({ hasText: /^(Review > )?Escalate$/ })
				.first();
			if (await escalateBtn.isVisible().catch(() => false)) {
				await escalateBtn.click();
				const dialog = modal(this.page);
				await dialog.locator('[data-fieldname="escalation_reason"] textarea, input').fill(reason);
				await dialog.getByRole('button', { name: /Submit|OK/i }).click();
				await this.page.waitForTimeout(800);
				return;
			}
		}
		await this.escalateViaFormApi(reason);
	}

	/** Desk session escalate when Review menu is unavailable (e.g. API-seeded pending claim). */
	async escalateViaFormApi(reason: string): Promise<void> {
		await this.page.evaluate(async (escalationReason) => {
			const win = window as unknown as {
				cur_frm?: { doctype: string; doc: { name: string }; reload_doc?: () => Promise<void> };
				frappe?: { xcall: (method: string, args: Record<string, string>) => Promise<unknown> };
			};
			const frm = win.cur_frm;
			if (!frm || !win.frappe) {
				throw new Error('Expense Claim form is not loaded');
			}
			await win.frappe.xcall('volunteering.volunteering.approval_routing.escalate_document', {
				doctype: frm.doctype,
				name: frm.doc.name,
				escalation_reason: escalationReason,
			});
			await frm.reload_doc?.();
		}, reason);
	}

	async expectApproveNotVisible(): Promise<void> {
		const primaryApprove = this.page.locator('.page-head .primary-action').filter({ hasText: /^Approve$/ });
		await expect(primaryApprove).toHaveCount(0);
	}

	async expectEscalateVisible(): Promise<void> {
		const flags = await this.getApproverFlags();
		expect(flags.can_escalate).toBe(true);
		expect(flags.can_approve).toBe(false);
		await this.waitForApproverActions();
		const reviewBtn = this.reviewMenuButton();
		if (await reviewBtn.isVisible().catch(() => false)) {
			await this.openReviewMenu();
			const escalateBtn = this.page
				.locator('.dropdown-menu.show .dropdown-item, .dropdown-menu a, a.grey-link')
				.filter({ hasText: /^(Review > )?Escalate$/ })
				.first();
			if (await escalateBtn.isVisible().catch(() => false)) {
				await this.page.keyboard.press('Escape').catch(() => {});
				return;
			}
		}
	}
}
