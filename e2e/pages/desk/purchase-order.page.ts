import type { Page } from '@playwright/test';
import { modal, resolvePostActionModal } from '../../helpers/dialogs';
import { DeskForm, formUrl } from '../../helpers/desk';

export class PurchaseOrderFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.page.goto('/desk', { waitUntil: 'domcontentloaded' });
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { frappe?: { set_route?: unknown } }).frappe?.set_route),
			undefined,
			{ timeout: 45000 },
		);
		await this.page.evaluate(() => {
			(
				window as unknown as {
					frappe: { set_route: (type: string, doctype: string, name: string) => void };
				}
			).frappe.set_route('Form', 'Purchase Order', 'new-purchase-order-1');
		});
		await this.waitForFormReady();
	}

	async open(name: string): Promise<void> {
		await this.page.goto(formUrl('Purchase Order', name), { waitUntil: 'domcontentloaded' });
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { frappe?: { set_route?: unknown } }).frappe?.set_route),
			undefined,
			{ timeout: 45000 },
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

	async fillPo(options: {
		supplier: string;
		project: string;
		amount: number;
		itemCode?: string;
	}): Promise<void> {
		const itemCode = options.itemCode || 'E2E Item';
		await this.page.evaluate(
			async ({ supplier, project, amount, item }) => {
				const win = window as unknown as {
					cur_frm?: {
						doc?: { company?: string; currency?: string; items?: unknown[] };
						clear_table: (table: string) => void;
						add_child: (table: string) => { doctype: string; name: string };
						set_value: (field: string, value: string | number) => Promise<unknown>;
						refresh_field: (table: string) => void;
						trigger?: (field: string) => void;
						cscript?: { calculate_taxes_and_totals?: () => void };
					};
					frappe?: {
						datetime: { get_today: () => string };
						defaults: { get_user_default: (key: string) => string };
						boot?: { sysdefaults?: { company?: string; currency?: string } };
						db: {
							get_doc: (dt: string, name: string) => Promise<{ item_name?: string; stock_uom?: string }>;
							get_value: (
								dt: string,
								name: string,
								field: string | string[],
							) => Promise<{ message?: Record<string, string> & { default_currency?: string } }>;
						};
						model: {
							set_value: (
								dt: string,
								name: string,
								field: string,
								value: string | number,
							) => Promise<void>;
						};
					};
				};
				const frm = win.cur_frm;
				if (!frm || !win.frappe) {
					throw new Error('Purchase Order form is not loaded');
				}
				const company =
					frm.doc?.company ||
					win.frappe.defaults.get_user_default('Company') ||
					win.frappe.boot?.sysdefaults?.company;
				if (company) {
					await frm.set_value('company', company);
				}
				const currencyRes = await win.frappe.db.get_value(
					'Company',
					company || '',
					'default_currency',
				);
				const currency =
					typeof currencyRes?.message === 'string'
						? currencyRes.message
						: currencyRes?.message?.default_currency ||
							win.frappe.boot?.sysdefaults?.currency ||
							'INR';
				await frm.set_value('currency', currency);
				await frm.set_value('conversion_rate', 1);
				const today = win.frappe.datetime.get_today();
				await frm.set_value('transaction_date', today);
				await frm.set_value('schedule_date', today);
				await frm.set_value('supplier', supplier);
				await frm.set_value('project', project);
				const ccRes = await win.frappe.db.get_value('Project', project, 'cost_center');
				const costCenter =
					typeof ccRes?.message === 'string' ? ccRes.message : ccRes?.message?.cost_center;
				if (costCenter) {
					await frm.set_value('cost_center', costCenter);
				}
				frm.clear_table('items');
				const row = frm.add_child('items');
				const itemDoc = await win.frappe.db.get_doc('Item', item);
				const uom = itemDoc.stock_uom || 'Nos';
				await win.frappe.model.set_value(row.doctype, row.name, 'item_code', item);
				await win.frappe.model.set_value(row.doctype, row.name, 'item_name', itemDoc.item_name || item);
				await win.frappe.model.set_value(row.doctype, row.name, 'uom', uom);
				await win.frappe.model.set_value(row.doctype, row.name, 'stock_uom', uom);
				await win.frappe.model.set_value(row.doctype, row.name, 'conversion_factor', 1);
				await win.frappe.model.set_value(row.doctype, row.name, 'qty', 1);
				await win.frappe.model.set_value(row.doctype, row.name, 'rate', amount);
				await win.frappe.model.set_value(row.doctype, row.name, 'base_rate', amount);
				await win.frappe.model.set_value(row.doctype, row.name, 'amount', amount);
				await win.frappe.model.set_value(row.doctype, row.name, 'base_amount', amount);
				await win.frappe.model.set_value(row.doctype, row.name, 'schedule_date', today);
				frm.refresh_field('items');
				frm.cscript?.calculate_taxes_and_totals?.();
				frm.trigger?.('project');
			},
			{
				supplier: options.supplier,
				project: options.project,
				amount: options.amount,
				item: itemCode,
			},
		);
		await this.page.waitForFunction(
			({ project, amount, item }) => {
				const doc = (
					window as unknown as {
						cur_frm?: {
							doc?: {
								supplier?: string;
								project?: string;
								grand_total?: number;
								items?: Array<{ item_code?: string; qty?: number; rate?: number }>;
							};
						};
					}
				).cur_frm?.doc;
				return Boolean(
					doc?.supplier &&
						doc?.project === project &&
						doc?.items?.length &&
						doc.items.some(
							(row) =>
								row.item_code === item &&
								Number(row.qty) === 1 &&
								Number(row.rate) === amount,
						),
				);
			},
			{
				project: options.project,
				amount: options.amount,
				item: itemCode,
			},
			{ timeout: 30000 },
		);
	}

	async saveDraft(): Promise<string> {
		await this.commitGridEdits();
		await this.dismissBlockingModals();
		const saveWait = this.waitForSaveResponse('Purchase Order');
		await this.clickPrimary('Save', { allowConfirm: true });
		const savedDoc = await saveWait.catch(() => null);
		if (savedDoc?.name) {
			return savedDoc.name;
		}
		return this.waitForPersistedDocName();
	}

	async saveAndSubmit(): Promise<string> {
		const name = await this.saveDraft();
		await this.submitSavedPoInSession(name);
		return name;
	}

	private async submitSavedPoInSession(name: string): Promise<void> {
		await this.open(name);
		const submitBtn = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Submit$/ })
			.first();
		if (await submitBtn.isVisible().catch(() => false)) {
			await submitBtn.click();
			await resolvePostActionModal(this.page, { allowConfirm: true });
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
			).frappe.db.get_doc('Purchase Order', docname);
			await (
				window as unknown as {
					frappe: { xcall: (method: string, args: Record<string, unknown>) => Promise<unknown> };
				}
			).frappe.xcall('frappe.model.workflow.apply_workflow', { doc, action: 'Submit' });
		}, name);
	}

	async approve(): Promise<void> {
		await this.dismissBlockingModals();
		const primaryApprove = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Approve$/ })
			.first();
		if (await primaryApprove.isVisible().catch(() => false)) {
			await this.clickWorkflowAction('Approve', { allowConfirm: true });
			return;
		}
		await this.page.evaluate(async () => {
			const docname = (window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc
				?.name;
			if (!docname) {
				throw new Error('Purchase Order form is not loaded');
			}
			const doc = await (
				window as unknown as {
					frappe: {
						db: { get_doc: (dt: string, name: string) => Promise<unknown> };
						xcall: (method: string, args: Record<string, unknown>) => Promise<unknown>;
					};
				}
			).frappe.db.get_doc('Purchase Order', docname);
			await (
				window as unknown as {
					frappe: { xcall: (method: string, args: Record<string, unknown>) => Promise<unknown> };
				}
			).frappe.xcall('frappe.model.workflow.apply_workflow', { doc, action: 'Approve' });
		});
	}

	async createPaymentEntry(): Promise<string> {
		await this.dismissBlockingModals();
		const createBtn = this.page
			.locator('.create-btn-group .btn, .inner-group-button, .btn-create')
			.filter({ hasText: /Create/i })
			.first();
		if (await createBtn.isVisible().catch(() => false)) {
			await createBtn.click();
			const paymentItem = this.page
				.locator('.dropdown-menu.show .dropdown-item, .dropdown-item')
				.filter({ hasText: /Payment Entry/i })
				.first();
			if (await paymentItem.isVisible({ timeout: 5000 }).catch(() => false)) {
				await paymentItem.click();
				await this.page.waitForURL(/payment-entry/, { timeout: 30000 });
			}
		}
		if (!this.page.url().includes('payment-entry')) {
			await this.page.evaluate(async () => {
				const win = window as unknown as {
					cur_frm?: { doc?: { name?: string } };
					frappe: {
						xcall: (method: string, args: Record<string, string>) => Promise<unknown>;
						model: { sync: (message: unknown) => Array<{ doctype: string; name: string }> };
						set_route: (type: string, doctype: string, name: string) => void;
					};
				};
				const docname = win.cur_frm?.doc?.name;
				if (!docname) {
					throw new Error('Purchase Order is not loaded');
				}
				const message = await win.frappe.xcall(
					'erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry',
					{ dt: 'Purchase Order', dn: docname },
				);
				const docs = win.frappe.model.sync(message);
				if (!docs?.[0]?.name) {
					throw new Error('Payment Entry mapper returned no document');
				}
				win.frappe.set_route('Form', docs[0].doctype, docs[0].name);
			});
		}
		await this.waitForFormReady();
		await this.page.evaluate(async () => {
			const win = window as unknown as {
				cur_frm?: {
					doc?: {
						company?: string;
						reference_no?: string;
						reference_date?: string;
						payment_type?: string;
					};
					set_value: (field: string, value: string) => Promise<unknown>;
				};
				frappe?: {
					datetime: { get_today: () => string };
					db: {
						get_value: (
							dt: string,
							name: string,
							field: string | string[],
						) => Promise<{ message?: Record<string, string> & { default_cash_account?: string } }>;
					};
				};
			};
			const frm = win.cur_frm;
			if (!frm || !win.frappe) {
				throw new Error('Payment Entry form is not loaded');
			}
			const company = frm.doc?.company;
			if (company && frm.doc?.payment_type === 'Pay') {
				const cashRes = await win.frappe.db.get_value('Company', company, 'default_cash_account');
				const cashAccount =
					typeof cashRes?.message === 'string'
						? cashRes.message
						: cashRes?.message?.default_cash_account;
				if (cashAccount) {
					await frm.set_value('mode_of_payment', 'Cash');
					await frm.set_value('paid_from', cashAccount);
				}
			}
			if (!frm.doc?.reference_no) {
				await frm.set_value('reference_no', `E2E-${Date.now()}`);
			}
			if (!frm.doc?.reference_date) {
				await frm.set_value('reference_date', win.frappe.datetime.get_today());
			}
		});
		const saveWait = this.waitForSaveResponse('Payment Entry');
		await this.clickPrimary('Save', { allowConfirm: true });
		const saved = await saveWait.catch(() => null);
		const peName = saved?.name || this.getDocNameFromUrl();
		if (!peName) {
			throw new Error('Payment Entry name not found after save');
		}
		const submitBtn = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Submit$/ })
			.first();
		if (await submitBtn.isVisible().catch(() => false)) {
			await submitBtn.click();
			for (let attempt = 0; attempt < 5; attempt++) {
				const confirmDialog = modal(this.page);
				const yesBtn = confirmDialog.getByRole('button', { name: /^Yes$/ });
				if (await yesBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
					await yesBtn.click();
					break;
				}
				await resolvePostActionModal(this.page, { allowConfirm: true });
				await this.page.waitForTimeout(400);
			}
		} else {
			await this.page.evaluate(async (docname) => {
				const doc = await (
					window as unknown as {
						frappe: {
							db: { get_doc: (dt: string, name: string) => Promise<unknown> };
							xcall: (method: string, args: Record<string, unknown>) => Promise<unknown>;
						};
					}
				).frappe.db.get_doc('Payment Entry', docname);
				await (
					window as unknown as {
						frappe: { xcall: (method: string, args: Record<string, unknown>) => Promise<unknown> };
					}
				).frappe.xcall('frappe.client.submit', { doc });
			}, peName);
		}
		const submitted = await this.page.evaluate(async (docname) => {
			const doc = await (
				window as unknown as {
					frappe: { db: { get_doc: (dt: string, name: string) => Promise<{ docstatus?: number }> } };
				}
			).frappe.db.get_doc('Payment Entry', docname);
			return doc?.docstatus === 1;
		}, peName);
		if (!submitted) {
			throw new Error(`Payment Entry ${peName} was not submitted`);
		}
		return peName;
	}
}
