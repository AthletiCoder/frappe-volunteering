import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class AttendanceRegularizationFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Attendance Regularization Request');
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Attendance Regularization Request', name);
	}

	async fillRequest(options: {
		date: string;
		requestedStatus: string;
		reason: string;
	}): Promise<void> {
		await this.fillDate('attendance_date', options.date);
		await this.fillSelect('requested_status', options.requestedStatus);
		await this.fillData('reason', options.reason);
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
		await this.clickWorkflowAction('Approve');
	}

	async reject(): Promise<void> {
		await this.clickWorkflowAction('Reject');
	}
}
