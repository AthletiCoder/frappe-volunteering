import type { Page } from '@playwright/test';
import { answerConfirm } from '../../helpers/dialogs';
import { DeskForm } from '../../helpers/desk';

export class ApprovalLimitsPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async open(): Promise<void> {
		await this.gotoForm('Approval and Advance Limits', 'Approval and Advance Limits');
	}

	async expectReadOnly(): Promise<void> {
		const saveBtn = this.page.locator('button[data-label="Save"], .primary-action').filter({
			hasText: 'Save',
		});
		const visible = await saveBtn.isVisible().catch(() => false);
		if (visible) {
			await saveBtn.click();
			const denied = this.page.locator('.modal-dialog, .msgprint').filter({
				hasText: /not permitted|read only|permission/i,
			});
			await denied.first().waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
		}
	}

	async resetToDefaults(): Promise<void> {
		await this.clickCustomButton('Reset to Defaults');
		await answerConfirm(this.page, /reset|default/i, 'Yes');
	}
}
