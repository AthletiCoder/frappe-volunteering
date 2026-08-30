import { expect } from '@playwright/test';
import { DeskForm, formUrl } from '../../helpers/desk';

export class PaymentEntryFormPage extends DeskForm {
	async openNew(): Promise<void> {
		await this.page.goto(formUrl('Payment Entry'), { waitUntil: 'domcontentloaded' });
		await this.waitForFormReady().catch(() => {});
	}

	async expectFormReachable(): Promise<void> {
		await this.openNew();
		await expect(this.page.locator('.form-layout:visible, .form-page:visible').first()).toBeVisible({
			timeout: 15000,
		});
	}

	async expectFormBlocked(): Promise<void> {
		await this.page.goto(formUrl('Payment Entry'), { waitUntil: 'domcontentloaded' });
		const denied = this.page.locator(
			'.msgprint, .modal-dialog, .forbidden, text=/Not permitted|Permission|403|not allowed/i',
		);
		const formVisible = await this.page
			.locator('.form-layout:visible, .form-page:visible')
			.first()
			.isVisible()
			.catch(() => false);
		if (!formVisible) {
			if (await denied.first().isVisible().catch(() => false)) {
				return;
			}
			const onPeRoute = this.page.url().includes('payment-entry');
			const hasLoadedForm = await this.page
				.evaluate(() => Boolean((window as unknown as { cur_frm?: { doc?: unknown } }).cur_frm?.doc))
				.catch(() => false);
			expect(onPeRoute && !hasLoadedForm).toBeTruthy();
			return;
		}
		await this.save({ expectError: /not permitted|permission|not allowed|cannot create/i });
	}
}
