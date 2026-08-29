import type { Page } from '@playwright/test';
import { modal } from '../../helpers/dialogs';
import { DeskForm } from '../../helpers/desk';

export class PurchaseInvoiceFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Purchase Invoice');
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Purchase Invoice', name);
	}

	async createFromPo(poName: string): Promise<void> {
		await this.openNew();
		await this.fillLink('purchase_order', poName);
	}

	async saveAndSubmit(): Promise<string> {
		await this.save();
		await this.submit();
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Purchase Invoice name not found after submit');
		}
		return name;
	}

	async markPaidOutside(remarks = 'E2E cash to vendor'): Promise<void> {
		await this.clickCustomButton('Mark Paid (outside system)');
		const dialog = modal(this.page);
		await dialog.locator('[data-fieldname="remarks"] textarea, input').fill(remarks);
		await dialog.getByRole('button', { name: /Create Payment Entry/i }).click();
		await this.page.waitForTimeout(1000);
	}
}
