import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class PurchaseOrderFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Purchase Order');
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Purchase Order', name);
	}

	async fillPo(options: {
		supplier: string;
		project: string;
		amount: number;
		itemCode?: string;
	}): Promise<void> {
		await this.fillLink('supplier', options.supplier);
		await this.fillLink('project', options.project);
		const grid = this.page.locator('[data-fieldname="items"]');
		await this.clearChildTable('items');
		await grid.getByRole('button', { name: /Add row/i }).click();
		const rowIndex = 0;
		await this.fillGridField('items', rowIndex, 'item_code', options.itemCode || 'E2E Item');
		await this.fillGridField('items', rowIndex, 'qty', '1');
		await this.fillGridField('items', rowIndex, 'rate', String(options.amount));
		await this.commitGridEdits();
	}

	async saveAndSubmit(): Promise<string> {
		await this.save();
		await this.submit({ allowConfirm: true });
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Purchase Order name not found after submit');
		}
		return name;
	}

	async approve(): Promise<void> {
		await this.clickWorkflowAction('Approve');
	}

	async createPaymentEntry(): Promise<string> {
		const createBtn = this.page
			.locator('.create-btn-group .btn, .inner-group-button')
			.filter({ hasText: 'Create' })
			.first();
		await createBtn.click();
		const paymentItem = this.page.locator('.dropdown-item').filter({ hasText: /Payment Entry/i }).first();
		await paymentItem.click();
		await this.page.waitForURL(/payment-entry/, { timeout: 30000 });
		await this.waitForFormReady();
		await this.save();
		await this.submit();
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Payment Entry name not found after submit');
		}
		return name;
	}
}
