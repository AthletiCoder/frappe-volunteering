import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class AttendanceRequestFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Attendance Request');
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Attendance Request', name);
	}

	async fillWfhRequest(date: string, explanation = 'E2E WFH request'): Promise<void> {
		await this.fillDate('from_date', date);
		await this.fillDate('to_date', date);
		await this.fillSelect('reason', 'Work From Home');
		await this.fillData('explanation', explanation);
	}

	async saveDraft(): Promise<string> {
		await this.save();
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Attendance Request name not found after save');
		}
		return name;
	}

	async submitRequest(): Promise<void> {
		await this.submit({ allowConfirm: true });
	}
}
