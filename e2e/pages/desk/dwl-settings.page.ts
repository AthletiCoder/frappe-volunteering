import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class DailyWorkLogSettingsPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async open(): Promise<void> {
		await this.gotoForm('Daily Work Log Settings', 'Daily Work Log Settings');
	}

	async setField(fieldname: string, value: string | number): Promise<void> {
		await this.fillData(fieldname, String(value));
		await this.save();
	}

	async previewSummary(): Promise<void> {
		await this.clickCustomButton('Preview Summary');
	}
}
