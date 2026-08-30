import type { Page } from '@playwright/test';
import { modal, resolvePostActionModal } from '../../helpers/dialogs';
import { DeskForm } from '../../helpers/desk';
import { PurchaseOrderFormPage } from './purchase-order.page';

export class PurchaseInvoiceFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Purchase Invoice');
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Purchase Invoice', name);
		await this.page.waitForFunction(
			(expected) =>
				(window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc?.name ===
				expected,
			name,
			{ timeout: 45000 },
		);
	}

	async createFromPo(poName: string): Promise<void> {
		await this.page.goto('/desk', { waitUntil: 'domcontentloaded' });
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { frappe?: { db?: unknown } }).frappe?.db),
			undefined,
			{ timeout: 45000 },
		);
		const poDocstatus = await this.page.evaluate(async (purchaseOrder) => {
			const doc = await (
				window as unknown as {
					frappe: { db: { get_doc: (dt: string, name: string) => Promise<{ docstatus?: number }> } };
				}
			).frappe.db.get_doc('Purchase Order', purchaseOrder);
			return doc.docstatus;
		}, poName);

		if (poDocstatus !== 1) {
			await this.openNew();
			await this.buildPurchaseInvoiceFromPoInSession(poName);
			await this.waitForFormReady();
			await this.page.waitForFunction(
				() =>
					Boolean(
						(window as unknown as { cur_frm?: { doc?: { items?: unknown[] } } }).cur_frm?.doc
							?.items?.length,
					),
				undefined,
				{ timeout: 30000 },
			);
			return;
		}

		const poPage = new PurchaseOrderFormPage(this.page);
		await poPage.open(poName);
		await this.dismissBlockingModals();
		let mapped = false;
		const createBtn = this.page
			.locator('.create-btn-group .btn, .inner-group-button, .btn-create')
			.filter({ hasText: /Create/i })
			.first();
		if (await createBtn.isVisible().catch(() => false)) {
			await createBtn.click();
			const piItem = this.page
				.locator('.dropdown-menu.show .dropdown-item, .dropdown-item')
				.filter({ hasText: /Purchase Invoice/i })
				.first();
			if (await piItem.isVisible({ timeout: 5000 }).catch(() => false)) {
				await piItem.click();
				mapped = await this.page
					.waitForURL(/purchase-invoice/, { timeout: 15000 })
					.then(() => true)
					.catch(() => false);
			}
		}
		if (!mapped) {
			const needsManualBuild = await this.page.evaluate(async (purchaseOrder) => {
				const doc = await (
					window as unknown as {
						frappe: { db: { get_doc: (dt: string, name: string) => Promise<{ docstatus?: number }> } };
					}
				).frappe.db.get_doc('Purchase Order', purchaseOrder);
				return doc.docstatus !== 1;
			}, poName);
			if (needsManualBuild) {
				await this.buildPurchaseInvoiceFromPoInSession(poName);
			} else {
				await this.mapPurchaseInvoiceFromPoInSession();
				await this.page.waitForURL(/purchase-invoice/, { timeout: 45000 });
			}
		}
		await this.waitForFormReady();
		await this.page.waitForFunction(
			(po) => {
				const doc = (
					window as unknown as {
						cur_frm?: { doc?: { items?: Array<{ purchase_order?: string }> } };
					}
				).cur_frm?.doc;
				if (doc?.items?.some((row) => row.purchase_order === po)) {
					return true;
				}
				return JSON.stringify(doc || {}).includes(po);
			},
			poName,
			{ timeout: 30000 },
		);
	}

	private async mapPurchaseInvoiceFromPoInSession(): Promise<void> {
		await this.page.evaluate(
			() =>
				new Promise<void>((resolve, reject) => {
					const win = window as unknown as {
						cur_frm?: { doc?: { name?: string } };
						frappe: {
							call: (opts: {
								method: string;
								args: Record<string, string>;
								freeze?: boolean;
								callback: (response: {
									exc?: string;
									message?: { doctype?: string; name?: string };
								}) => void;
								error?: (response: { message?: string; exc?: string }) => void;
							}) => void;
							model: { sync: (message: unknown) => Array<{ doctype: string; name: string }> };
							set_route: (type: string, doctype: string, name: string) => void;
						};
					};
					const sourceName = win.cur_frm?.doc?.name;
					if (!sourceName) {
						reject(new Error('Purchase Order form is not loaded'));
						return;
					}
					win.frappe.call({
						method: 'frappe.model.mapper.make_mapped_doc',
						args: {
							method:
								'erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice',
							source_name: sourceName,
						},
						freeze: true,
						callback: (response) => {
							if (response.exc) {
								reject(new Error(response.exc));
								return;
							}
							const synced = win.frappe.model.sync(response.message);
							const doc = synced?.[0] || response.message;
							if (!doc?.doctype || !doc?.name) {
								reject(new Error('Purchase Invoice mapper returned no document'));
								return;
							}
							win.frappe.set_route('Form', doc.doctype, doc.name);
							resolve();
						},
						error: (response) =>
							reject(
								new Error(
									response.message || response.exc || 'Purchase Invoice mapper failed',
								),
							),
					});
				}),
		);
	}

	private async buildPurchaseInvoiceFromPoInSession(poName: string): Promise<void> {
		await this.page.evaluate(async (purchaseOrder) => {
			const win = window as unknown as {
				frappe: {
					db: {
						get_doc: (
							dt: string,
							name: string,
						) => Promise<{
							supplier: string;
							company: string;
							project?: string;
							currency?: string;
							items: Array<{
								name: string;
								item_code: string;
								item_name?: string;
								qty: number;
								rate: number;
								uom?: string;
								stock_uom?: string;
							}>;
						}>;
					};
					new_doc: (doctype: string) => void;
					model: {
						set_value: (
							dt: string,
							name: string,
							field: string,
							value: string | number,
						) => Promise<void>;
					};
					set_route: (type: string, doctype: string, name: string) => void;
				};
				cur_frm?: {
					set_value: (field: string, value: string) => Promise<unknown>;
					clear_table: (table: string) => void;
					add_child: (table: string) => { doctype: string; name: string };
					refresh_field: (table: string) => void;
				};
			};
			const poDoc = await win.frappe.db.get_doc('Purchase Order', purchaseOrder);
			if (
				!(win as unknown as { cur_frm?: { doctype?: string } }).cur_frm ||
				(win as unknown as { cur_frm?: { doctype?: string } }).cur_frm?.doctype !==
					'Purchase Invoice'
			) {
				win.frappe.new_doc('Purchase Invoice');
			}
			const frm = (win as unknown as {
				cur_frm?: {
					set_value: (field: string, value: string) => Promise<unknown>;
					clear_table: (table: string) => void;
					add_child: (table: string) => { doctype: string; name: string };
					refresh_field: (table: string) => void;
				};
			}).cur_frm;
			if (!frm) {
				throw new Error('Purchase Invoice form is not loaded');
			}
			await frm.set_value('supplier', poDoc.supplier);
			await frm.set_value('company', poDoc.company);
			if (poDoc.project) {
				await frm.set_value('project', poDoc.project);
			}
			if (poDoc.currency) {
				await frm.set_value('currency', poDoc.currency);
			}
			frm.clear_table('items');
			for (const row of poDoc.items) {
				const child = frm.add_child('items');
				await win.frappe.model.set_value(child.doctype, child.name, 'item_code', row.item_code);
				await win.frappe.model.set_value(
					child.doctype,
					child.name,
					'item_name',
					row.item_name || row.item_code,
				);
				await win.frappe.model.set_value(child.doctype, child.name, 'qty', row.qty);
				await win.frappe.model.set_value(child.doctype, child.name, 'rate', row.rate);
				await win.frappe.model.set_value(child.doctype, child.name, 'uom', row.uom || row.stock_uom || 'Nos');
				await win.frappe.model.set_value(child.doctype, child.name, 'purchase_order', purchaseOrder);
				await win.frappe.model.set_value(child.doctype, child.name, 'po_detail', row.name);
			}
			frm.refresh_field('items');
			const docname = (window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc
				?.name;
			if (!docname) {
				throw new Error('Purchase Invoice draft was not created');
			}
			win.frappe.set_route('Form', 'Purchase Invoice', docname);
		}, poName);
	}

	async saveDraft(): Promise<string> {
		await this.commitGridEdits();
		await this.dismissBlockingModals();
		const saveWait = this.waitForSaveResponse('Purchase Invoice');
		await this.clickPrimary('Save', { allowConfirm: true });
		const savedDoc = await saveWait.catch(() => null);
		if (savedDoc?.name) {
			return savedDoc.name;
		}
		return this.waitForPersistedDocName();
	}

	async saveAndSubmit(): Promise<string> {
		const name = await this.saveDraft();
		await this.open(name);
		const submitBtn = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Submit$/ })
			.first();
		if (await submitBtn.isVisible().catch(() => false)) {
			await submitBtn.click();
			await resolvePostActionModal(this.page, { allowConfirm: true });
		} else {
			await this.page.evaluate(async (docname) => {
				const doc = await (
					window as unknown as {
						frappe: {
							db: { get_doc: (dt: string, name: string) => Promise<unknown> };
							xcall: (method: string, args: Record<string, unknown>) => Promise<unknown>;
						};
					}
				).frappe.db.get_doc('Purchase Invoice', docname);
				await (
					window as unknown as {
						frappe: { xcall: (method: string, args: Record<string, unknown>) => Promise<unknown> };
					}
				).frappe.xcall('frappe.model.workflow.apply_workflow', { doc, action: 'Submit' });
			}, name);
		}
		return name;
	}

	async markPaidOutside(remarks = 'E2E cash to vendor'): Promise<void> {
		await this.page.evaluate(async () => {
			const frm = (window as unknown as { cur_frm?: { reload_doc?: () => Promise<unknown> } })
				.cur_frm;
			if (frm?.reload_doc) {
				await frm.reload_doc();
			}
		});
		await this.page.waitForFunction(
			() => {
				const doc = (
					window as unknown as {
						cur_frm?: { doc?: { docstatus?: number; outstanding_amount?: number } };
					}
				).cur_frm?.doc;
				return doc?.docstatus === 1 && Number(doc?.outstanding_amount) > 0;
			},
			undefined,
			{ timeout: 30000 },
		);
		const directBtn = this.page
			.locator('.custom-btn, button')
			.filter({ hasText: 'Mark Paid (outside system)' })
			.first();
		if (await directBtn.isVisible().catch(() => false)) {
			await directBtn.click();
		} else {
			await this.openMenuAction('Mark Paid (outside system)');
		}
		const dialog = modal(this.page);
		await dialog.locator('[data-fieldname="remarks"] textarea').fill(remarks);
		const payWait = this.page.waitForResponse(
			(response) =>
				response.request().method() === 'POST' &&
				response.url().includes('mark_purchase_invoice_paid_outside'),
			{ timeout: 60000 },
		);
		await dialog.getByRole('button', { name: /Create Payment Entry/i }).click();
		await payWait;
		await this.page.waitForTimeout(500);
	}
}
