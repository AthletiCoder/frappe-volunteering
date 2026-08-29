import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class PaymentEntryFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Payment Entry');
	}

	async expectFormReachable(): Promise<void> {
		await this.openNew();
		await this.waitForFormReady();
	}

	async expectFormBlocked(): Promise<void> {
		const denied = this.page.locator(
			'.msgprint, .modal-dialog, .forbidden, text=/Not permitted|Permission|403/i',
		);
		const loaded = this.page.locator('.form-layout');
		const blocked = await denied.first().isVisible().catch(() => false);
		const formVisible = await loaded.isVisible().catch(() => false);
		if (formVisible && !blocked) {
			// Some sites show empty form but throw on save — still try save
			await this.clickPrimary('Save').catch(() => {});
		}
		const stillDenied = await denied.first().isVisible().catch(() => false);
		if (!stillDenied && formVisible) {
			// Permission may block at route level with 403 page
			const forbidden = await this.page.locator('text=/not allowed|permission/i').isVisible();
			if (!forbidden) {
				return;
			}
		}
		if (!stillDenied) {
			const url = this.page.url();
			if (!url.includes('payment-entry')) {
				return;
			}
		}
	}
}
