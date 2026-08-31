import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class AttendanceRegularizationFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Attendance Regularization Request');
		await this.waitForEmployeeDefault();
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Attendance Regularization Request', name);
	}

	private async waitForEmployeeDefault(): Promise<void> {
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { cur_frm?: { doc?: { employee?: string } } }).cur_frm?.doc?.employee),
			undefined,
			{ timeout: 15000 },
		);
	}

	async fillRequest(options: {
		date: string;
		requestedStatus: string;
		reason: string;
	}): Promise<void> {
		await this.waitForEmployeeDefault();
		await this.fillDate('attendance_date', options.date);
		await this.fillSelect('requested_status', options.requestedStatus);
		await this.fillData('reason', options.reason);
	}

	async saveDraft(): Promise<string> {
		await this.save();
		const name = this.getDocNameFromUrl();
		if (!name) {
			return this.waitForPersistedDocName();
		}
		return name;
	}

	async saveAndSubmit(): Promise<string> {
		await this.save();
		await this.submit();
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Attendance Regularization name not found after submit');
		}
		return name;
	}

	async approve(): Promise<void> {
		try {
			await this.openMenuAction('Approve');
		} catch {
			await this.page.evaluate(() => {
				const frm = (window as unknown as {
					cur_frm?: { call: (m: string) => Promise<unknown>; reload_doc: () => void };
				}).cur_frm;
				return frm?.call('approve_request').then(() => frm?.reload_doc());
			});
		}
		await this.page.waitForTimeout(500);
	}

	async reject(): Promise<void> {
		try {
			await this.openMenuAction('Reject');
		} catch {
			await this.page.evaluate(() => {
				const frm = (window as unknown as {
					cur_frm?: { call: (m: string) => Promise<unknown>; reload_doc: () => void };
				}).cur_frm;
				return frm?.call('reject_request').then(() => frm?.reload_doc());
			});
		}
		await this.page.waitForTimeout(500);
	}
}
