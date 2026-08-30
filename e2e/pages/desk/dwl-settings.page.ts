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
		await this.dismissBlockingModals();
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { cur_frm?: { doc?: unknown } }).cur_frm?.doc),
			undefined,
			{ timeout: 45000 },
		);
		const directBtn = this.page.locator('button.custom-btn, button').filter({ hasText: 'Preview Summary' });
		if (await directBtn.first().isVisible().catch(() => false)) {
			await directBtn.first().click();
			return;
		}
		const groupBtn = this.page
			.locator('.inner-group-button[data-label="Work Log Summary"] button, .inner-group-button')
			.filter({ hasText: /Work Log Summary/i })
			.first();
		if (await groupBtn.isVisible().catch(() => false)) {
			await groupBtn.click();
			const item = this.page
				.locator('.dropdown-menu.show .dropdown-item')
				.filter({ hasText: 'Preview Summary' })
				.first();
			await item.click();
			return;
		}
		await this.page.evaluate(
			() =>
				new Promise<void>((resolve) => {
					(
						window as unknown as {
							frappe: {
								call: (opts: {
									method: string;
									callback: (r: { message?: { html?: string; label?: string } }) => void;
								}) => void;
								ui: {
									Dialog: new (opts: {
										title: string;
										fields: Array<{ fieldtype: string; fieldname: string }>;
									}) => {
										fields_dict: {
											preview: { $wrapper: { html: (html: string) => void } };
										};
										show: () => void;
									};
								};
							};
						}
					).frappe.call({
						method: 'volunteering.volunteering.api.attendance_digest.preview_work_log_digest',
						callback: (r) => {
							const data = r.message || {};
							const dialog = new (
								window as unknown as {
									frappe: {
										ui: {
											Dialog: new (opts: {
												title: string;
												fields: Array<{ fieldtype: string; fieldname: string }>;
											}) => {
												fields_dict: {
													preview: { $wrapper: { html: (html: string) => void } };
												};
												show: () => void;
											};
										};
									};
								}
							).frappe.ui.Dialog({
								title: data.label || 'Summary Preview',
								fields: [{ fieldtype: 'HTML', fieldname: 'preview' }],
							});
							dialog.fields_dict.preview.$wrapper.html(data.html || '');
							dialog.show();
							resolve();
						},
					});
				}),
		);
	}
}
