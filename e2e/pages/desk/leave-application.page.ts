import type { Page } from '@playwright/test';
import { resolvePostActionModal } from '../../helpers/dialogs';
import { DeskForm } from '../../helpers/desk';

export class LeaveApplicationFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Leave Application');
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Leave Application', name);
	}

	async setEmployee(employeeId: string): Promise<void> {
		await this.fillLink('employee', employeeId);
	}

	async saveDraft(): Promise<string> {
		const saveWait = this.waitForSaveResponse('Leave Application');
		await this.save();
		const savedDoc = await saveWait.catch(() => null);
		if (savedDoc?.name) {
			return savedDoc.name;
		}
		return this.waitForPersistedDocName();
	}

	async fillLeave(options: {
		fromDate: string;
		toDate: string;
		category?: string;
		leaveType?: string;
		description?: string;
		leaveApprover?: string;
	}): Promise<void> {
		if (options.category) {
			await this.fillSelect('leave_category', options.category);
		}
		if (options.leaveType) {
			await this.fillLink('leave_type', options.leaveType);
		}
		await this.fillDate('from_date', options.fromDate);
		await this.fillDate('to_date', options.toDate);
		if (options.description) {
			await this.fillData('description', options.description);
		} else {
			await this.fillData('description', 'E2E leave application');
		}
		if (options.leaveApprover) {
			await this.fillLink('leave_approver', options.leaveApprover);
		}
	}

	async saveAndSubmit(): Promise<string> {
		const name = await this.saveDraft();
		await this.submitSavedLeaveInSession(name);
		const fromUrl = this.getDocNameFromUrl();
		if (fromUrl) {
			return fromUrl;
		}
		const fromFrm = await this.page.evaluate(
			() =>
				(window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc?.name || null,
		);
		if (fromFrm && !fromFrm.startsWith('new-')) {
			return fromFrm;
		}
		return name;
	}

	private async submitSavedLeaveInSession(name: string): Promise<void> {
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
						db: { get_doc: (dt: string, n: string) => Promise<unknown> };
						call: (opts: { method: string; args: Record<string, unknown> }) => Promise<unknown>;
					};
				}
			).frappe.db.get_doc('Leave Application', docname);
			await (
				window as unknown as {
					frappe: { call: (opts: { method: string; args: Record<string, unknown> }) => Promise<unknown> };
				}
			).frappe.call({ method: 'frappe.client.submit', args: { doc } });
		}, name);
		await this.page
			.waitForFunction(
				() => {
					const doc = (window as unknown as {
						cur_frm?: { doc?: { docstatus?: number } };
					}).cur_frm?.doc;
					return doc?.docstatus === 1;
				},
				undefined,
				{ timeout: 30000 },
			)
			.catch(() => {});
	}

	async approve(): Promise<void> {
		await this.clickWorkflowAction('Approve');
	}

	async reject(): Promise<void> {
		await this.clickWorkflowAction('Reject');
	}

	async setStatus(status: 'Approved' | 'Rejected' | 'Open'): Promise<void> {
		await this.fillSelect('status', status);
		await this.save();
		if (status !== 'Open') {
			await this.submit();
		}
	}
}
