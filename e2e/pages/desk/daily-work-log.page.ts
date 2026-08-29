import { expect, type Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export interface WorkLogItem {
	project?: string;
	hours: number;
	taskTitle?: string;
	description?: string;
	skipProject?: boolean;
}

export class DailyWorkLogFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Daily Work Log');
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Daily Work Log', name);
	}

	async setDate(isoDate: string): Promise<void> {
		await this.fillDate('date', isoDate);
		await this.page.waitForTimeout(500);
	}

	async setEmployee(employeeId: string): Promise<void> {
		await this.fillLink('employee', employeeId);
	}

	async addItem(item: WorkLogItem & { skipProject?: boolean }): Promise<void> {
		const grid = this.page.locator('[data-fieldname="items"]');
		await grid.scrollIntoViewIfNeeded();
		await this.clearChildTable('items');
		await grid.getByRole('button', { name: /Add row/i }).click();
		await grid.getByRole('textbox', { name: 'Task Title' }).waitFor({ state: 'visible', timeout: 15000 });
		await grid.getByRole('textbox', { name: 'Task Title' }).fill(item.taskTitle || 'E2E Task');

		if (!item.skipProject) {
			if (!item.project) {
				throw new Error('addItem requires project unless skipProject is true');
			}
			const project = grid.getByRole('combobox', { name: 'Project' });
			await project.fill(item.project);
			const option = this.page
				.locator('.awesomplete ul li, [role="option"]')
				.filter({ hasText: item.project })
				.first();
			if (await option.isVisible({ timeout: 5000 }).catch(() => false)) {
				await option.click();
			} else {
				await project.press('ArrowDown');
				await project.press('Enter');
			}
		}

		await grid
			.getByRole('textbox', { name: 'Description' })
			.fill(item.description || 'E2E daily work log task description here');
		await grid.getByRole('textbox', { name: 'Time Spent (Hours)' }).fill(String(item.hours));
		await this.commitGridEdits();
	}

	async expectWfhAutoApplied(): Promise<void> {
		const dateField = this.field('date');
		await expect(dateField.locator('.help-box, .control-description')).toContainText(
			/Work From Home|approved Attendance Request/i,
			{ timeout: 15000 },
		);
	}

	async forceWfhFlag(checked: boolean): Promise<void> {
		await this.page.evaluate((value) => {
			const frm = (window as unknown as { cur_frm?: { set_value: (f: string, v: number) => void } })
				.cur_frm;
			frm?.set_value('is_wfh', value ? 1 : 0);
		}, checked);
	}

	async saveAndSubmit(options?: { expectLowHoursWarning?: boolean }): Promise<string> {
		const warning = /below|minimum|recommended/i;
		if (options?.expectLowHoursWarning) {
			await this.save({ expectWarning: warning });
			await this.submit({ allowConfirm: true });
		} else {
			await this.save();
			await this.submit();
		}
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Daily Work Log name not found in URL after submit');
		}
		return name;
	}

	async markReviewed(remarks = 'Reviewed in E2E'): Promise<void> {
		await this.fillData('manager_remarks', remarks);
		await this.clickCustomButton('Mark as Reviewed');
	}
}
