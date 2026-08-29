import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class AccountingSettingsPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async open(): Promise<void> {
		await this.gotoForm('Volunteering Accounting Settings', 'Volunteering Accounting Settings');
	}

	async setField(fieldname: string, value: string | number): Promise<void> {
		const str = String(value);
		const control = this.field(fieldname);
		const checkbox = control.locator('input[type="checkbox"]');
		if (await checkbox.count()) {
			if (str === '1' || str === 'true') {
				await checkbox.check();
			} else {
				await checkbox.uncheck();
			}
		} else {
			await this.fillData(fieldname, str);
		}
		await this.save();
	}
}
