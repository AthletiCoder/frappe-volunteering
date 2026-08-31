import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class EmployeeFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async open(employeeId: string): Promise<void> {
		await this.gotoForm('Employee', employeeId);
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
