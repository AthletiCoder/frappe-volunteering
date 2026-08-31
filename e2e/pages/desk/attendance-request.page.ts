import { expect, type Page } from '@playwright/test';
import { dismissVisibleModal, resolvePostActionModal } from '../../helpers/dialogs';
import { DeskForm } from '../../helpers/desk';

export class AttendanceRequestFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Attendance Request');
		await this.waitForEmployeeDefault();
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Attendance Request', name);
		for (let i = 0; i < 5; i++) {
			await this.dismissBlockingModals();
			const modal = this.page.locator('.modal.show');
			if (!(await modal.isVisible().catch(() => false))) {
				break;
			}
			await dismissVisibleModal(this.page);
		}
	}

	private async waitForEmployeeDefault(): Promise<void> {
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { cur_frm?: { doc?: { employee?: string } } }).cur_frm?.doc?.employee),
			undefined,
			{ timeout: 15000 },
		);
	}

	async fillWfhRequest(date: string, explanation = 'E2E WFH request'): Promise<void> {
		await this.waitForEmployeeDefault();
		await this.fillDate('from_date', date);
		await this.fillDate('to_date', date);
		await this.fillSelect('reason', 'Work From Home');
		await this.fillData('explanation', explanation);
	}

	async saveDraft(): Promise<string> {
		await this.save();
		const name = this.getDocNameFromUrl();
		if (!name) {
			return this.waitForPersistedDocName();
		}
		return name;
	}

	async submitRequest(options?: { expectError?: RegExp | string }): Promise<void> {
		await this.dismissBlockingModals();
		await this.submit({ allowConfirm: true, ...options });
		if (options?.expectError) {
			return;
		}
		const submitted = await this.page.evaluate(
			() => (window as unknown as { cur_frm?: { doc?: { docstatus?: number } } }).cur_frm?.doc?.docstatus === 1,
		);
		if (submitted) {
			return;
		}
		const name = this.getDocNameFromUrl();
		if (!name) {
			return;
		}
		await this.syncFormToSavedDoc('Attendance Request', name);
		await this.dismissBlockingModals();
		await this.submitSavedInSession('Attendance Request');
	}

	async expectEmployeeSubmitHidden(): Promise<void> {
		await this.dismissBlockingModals();
		const submitBtn = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Submit$/ });
		await expect(submitBtn).toHaveCount(0);
	}

	private async submitSavedInSession(doctype: string): Promise<void> {
		await this.dismissBlockingModals();
		const submitBtn = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Submit$/ })
			.first();
		if (await submitBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
			await submitBtn.click({ force: true });
			await resolvePostActionModal(this.page, { allowConfirm: true });
			return;
		}
		await this.page.evaluate(async (dt) => {
			const name = (window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc?.name;
			if (!name) {
				return;
			}
			const doc = await (
				window as unknown as {
					frappe: { db: { get_doc: (d: string, n: string) => Promise<unknown> } };
				}
			).frappe.db.get_doc(dt, name);
			await (
				window as unknown as {
					frappe: { call: (opts: { method: string; args: Record<string, unknown> }) => Promise<unknown> };
				}
			).frappe.call({ method: 'frappe.client.submit', args: { doc } });
		}, doctype);
	}
}
