import type { Page } from '@playwright/test';
import { expectMsgprint } from '../../helpers/dialogs';
import { DeskForm } from '../../helpers/desk';

export class EmployeeAdvanceFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Employee Advance');
		await this.dismissBlockingModals();
		await this.dismissFormOverlays();
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Employee Advance', name);
	}

	async fillAdvance(amount: number, purpose = 'E2E advance'): Promise<void> {
		await this.ensureAdvanceAmountFieldsVisible();
		await this.fillData('purpose', purpose);
		await this.fillFloat('advance_amount', amount);
	}

	/** Purpose & amount live on Details; older tab layouts put them after Approval tab break. */
	private async ensureAdvanceAmountFieldsVisible(): Promise<void> {
		if (await this.field('purpose').isVisible().catch(() => false)) {
			return;
		}
		await this.clickTab('Approval & Routing');
	}

	async fillEmployeeAsAccounts(_employeeName: string, employeeId: string): Promise<void> {
		const control = await this.ensureFieldVisible('employee');
		const linkBtn = control.locator('.link-btn, .btn-open').first();
		if (await linkBtn.isVisible().catch(() => false)) {
			await linkBtn.click();
		} else {
			const input = control.getByRole('combobox').first().or(control.locator('input').first());
			await input.click();
			await input.fill('E2E');
			await this.page.waitForTimeout(500);
			await this.page.getByText('Advanced Search', { exact: true }).click({ force: true });
		}
		await this.pickFromLinkDialog(employeeId, undefined, 'E2E Employee A');
		await this.page.waitForFunction(
			(id) =>
				(window as unknown as { cur_frm?: { doc?: { employee?: string } } }).cur_frm?.doc?.employee === id,
			employeeId,
			{ timeout: 15000 },
		);
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { cur_frm?: { doc?: { company?: string } } }).cur_frm?.doc?.company),
			undefined,
			{ timeout: 15000 },
		);
	}

	async saveDraft(): Promise<string> {
		await this.save();
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Employee Advance name not found after save');
		}
		return name;
	}

	async saveAndSubmit(options?: { expectReplenishWarning?: boolean }): Promise<string> {
		if (options?.expectReplenishWarning) {
			await this.save({ expectWarning: /leftover|residual|replenish/i });
		} else {
			await this.save();
		}
		await this.submit({ allowConfirm: true });
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Employee Advance name not found after submit');
		}
		return name;
	}

	async approve(): Promise<void> {
		await this.clickWorkflowAction('Approve');
	}
}
