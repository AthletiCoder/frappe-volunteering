import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class EmployeeFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async open(employeeId: string): Promise<void> {
		await this.page.goto('/desk', { waitUntil: 'domcontentloaded' });
		await this.page.waitForFunction(
			() => Boolean((window as unknown as { frappe?: { set_route?: unknown } }).frappe?.set_route),
			undefined,
			{ timeout: 45000 },
		);
		await this.page.evaluate((name) => {
			(
				window as unknown as {
					frappe: { set_route: (type: string, doctype: string, docname: string) => void };
				}
			).frappe.set_route('Form', 'Employee', name);
		}, employeeId);
		await this.page.waitForFunction(
			(expected) =>
				(window as unknown as { cur_frm?: { doc?: { name?: string } } }).cur_frm?.doc?.name ===
				expected,
			employeeId,
			{ timeout: 45000 },
		);
		await this.page.waitForFunction(
			() =>
				document.querySelectorAll('.form-layout .frappe-control, .form-page .frappe-control')
					.length > 0,
			undefined,
			{ timeout: 45000 },
		);
		await this.dismissBlockingModals();
	}

	async setReportsTo(managerEmployeeId: string): Promise<void> {
		await this.fillLink('reports_to', managerEmployeeId);
		await this.save();
	}

	async setField(fieldname: string, value: string): Promise<void> {
		if (fieldname === 'department' || fieldname === 'designation' || fieldname === 'grade') {
			await this.fillLink(fieldname, value);
		} else if (fieldname === 'employment_type') {
			await this.fillLink('employment_type', value);
		} else {
			await this.fillData(fieldname, value);
		}
		await this.save();
	}

	async readField(fieldname: string): Promise<string> {
		if (fieldname === 'leave_approver') {
			return this.readLinkValue('leave_approver');
		}
		return this.readDataValue(fieldname);
	}
}
