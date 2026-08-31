import type { Page } from '@playwright/test';
import { expectMsgprint, resolvePostActionModal } from '../../helpers/dialogs';
import { DeskForm } from '../../helpers/desk';

export class EmployeeAdvanceFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Employee Advance');
		await this.dismissBlockingModals();
		await this.dismissFormOverlays();
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { cur_frm?: { doc?: unknown } }).cur_frm?.doc),
			undefined,
			{ timeout: 45000 },
		);
		await this.ensureSelfEmployee();
	}

	private async ensureSelfEmployee(): Promise<void> {
		await this.page.evaluate(async () => {
			const win = window as unknown as {
				cur_frm?: {
					doc?: { employee?: string; company?: string };
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
				};
			};
			const frm = win.cur_frm;
			if (!frm || !win.frappe) {
				return;
			}
			if (!frm.doc?.employee) {
				const res = await win.frappe.db.get_value('Employee', { user_id: win.frappe.session.user }, 'name');
				const name = res?.message?.name;
				if (name) {
					await frm.set_value('employee', name);
				}
			}
			frm.trigger?.('employee');
			if (frm.doc?.employee && !frm.doc?.company) {
				const empRes = await win.frappe.db.get_value('Employee', frm.doc.employee, 'company');
				const company =
					typeof empRes?.message === 'string' ? empRes.message : empRes?.message?.company;
				if (company) {
					await frm.set_value('company', company);
				}
			}
		});
	}

	async fillAdvance(amount: number, purpose = 'E2E advance'): Promise<void> {
		await this.ensureSelfEmployee();
		await this.page.evaluate(
			async ({ amt, text }) => {
				const frm = (window as unknown as {
					cur_frm?: { set_value: (f: string, v: string | number) => Promise<unknown> };
				}).cur_frm;
				if (!frm) {
					return;
				}
				await frm.set_value('purpose', text);
				await frm.set_value('advance_amount', amt);
			},
			{ amt: amount, text: purpose },
		);
	}

	async fillEmployeeAsAccounts(_employeeName: string, employeeId: string): Promise<void> {
		await this.page.evaluate(async (id) => {
			const win = window as unknown as {
				cur_frm?: {
					doc?: { employee?: string; company?: string };
					set_value: (f: string, v: string) => Promise<unknown>;
					trigger?: (e: string) => void;
				};
				frappe?: {
					db: {
						get_value: (
							dt: string,
							name: string,
							field: string,
						) => Promise<{ message?: { company?: string } }>;
					};
				};
			};
			const frm = win.cur_frm;
			if (!frm || !win.frappe) {
				throw new Error('Employee Advance form is not loaded');
			}
			await frm.set_value('employee', id);
			frm.trigger?.('employee');
			if (!frm.doc?.company) {
				const empRes = await win.frappe.db.get_value('Employee', id, 'company');
				const company =
					typeof empRes?.message === 'string' ? empRes.message : empRes?.message?.company;
				if (company) {
					await frm.set_value('company', company);
				}
			}
		}, employeeId);
		await this.page.waitForFunction(
			(id) =>
				(window as unknown as { cur_frm?: { doc?: { employee?: string } } }).cur_frm?.doc?.employee ===
				id,
			employeeId,
			{ timeout: 15000 },
		);
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Employee Advance', name);
		const docLoaded = await this.page
			.waitForFunction(
				(expected) =>
					(window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc?.name ===
					expected,
				name,
				{ timeout: 15000 },
			)
			.then(() => true)
			.catch(() => false);
		if (!docLoaded) {
			await this.page.goto('/desk', { waitUntil: 'domcontentloaded' });
			await this.page.waitForFunction(
				() => Boolean((window as unknown as { frappe?: { set_route?: unknown } }).frappe?.set_route),
				undefined,
				{ timeout: 45000 },
			);
			await this.page.evaluate((docname) => {
				(
					window as unknown as {
						frappe: { set_route: (type: string, doctype: string, name: string) => void };
					}
				).frappe.set_route('Form', 'Employee Advance', docname);
			}, name);
		}
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
	}

	async saveDraft(): Promise<string> {
		const saveWait = this.waitForSaveResponse('Employee Advance');
		await this.save();
		const savedDoc = await saveWait.catch(() => null);
		if (savedDoc) {
			return savedDoc.name;
		}
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Employee Advance name not found after save');
		}
		return name;
	}

	async saveAndSubmit(options?: { expectReplenishWarning?: boolean }): Promise<string> {
		const saveWait = this.waitForSaveResponse('Employee Advance');
		if (options?.expectReplenishWarning) {
			await this.save({ expectWarning: /leftover|residual|replenish/i });
		} else {
			await this.save();
		}
		const savedDoc = await saveWait.catch(() => null);
		const name = savedDoc?.name || this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Employee Advance name not found after save');
		}
		await this.submitSavedAdvanceInSession(name);
		return name;
	}

	private async submitSavedAdvanceInSession(name: string): Promise<void> {
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
			).frappe.db.get_doc('Employee Advance', docname);
			await (
				window as unknown as {
					frappe: { xcall: (method: string, args: Record<string, unknown>) => Promise<unknown> };
				}
			).frappe.xcall('frappe.model.workflow.apply_workflow', { doc, action: 'Submit' });
		}, name);
	}

	async approve(): Promise<void> {
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
		const primaryApprove = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Approve$/ })
			.first();
		if (await primaryApprove.isVisible().catch(() => false)) {
			await this.clickWorkflowAction('Approve', { allowConfirm: true });
			return;
		}
		await this.page.evaluate(async () => {
			const win = window as unknown as {
				cur_frm?: { doc?: { name?: string } };
				frappe?: {
					db: { get_doc: (dt: string, name: string) => Promise<unknown> };
					xcall: (method: string, args: Record<string, unknown>) => Promise<unknown>;
				};
			};
			const docname = win.cur_frm?.doc?.name;
			if (!docname || !win.frappe) {
				throw new Error('Employee Advance form is not loaded');
			}
			const doc = await win.frappe.db.get_doc('Employee Advance', docname);
			await win.frappe.xcall('frappe.model.workflow.apply_workflow', { doc, action: 'Approve' });
		});
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
}
