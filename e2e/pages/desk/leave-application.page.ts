import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class LeaveApplicationFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Leave Application');
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Leave Application', name);
	}

	async setEmployee(employeeId: string): Promise<void> {
		await this.fillLink('employee', employeeId);
	}

	async saveDraft(): Promise<string> {
		await this.save();
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Leave Application name not found after save');
		}
		return name;
	}

	async fillLeave(options: {
		fromDate: string;
		toDate: string;
		category?: string;
		leaveType?: string;
		description?: string;
		leaveApprover?: string;
	}): Promise<void> {
		if (options.category) {
			await this.fillSelect('leave_category', options.category);
		}
		if (options.leaveType) {
			await this.fillLink('leave_type', options.leaveType);
		}
		await this.fillDate('from_date', options.fromDate);
		await this.fillDate('to_date', options.toDate);
		if (options.description) {
			await this.fillData('description', options.description);
		} else {
			await this.fillData('description', 'E2E leave application');
		}
		if (options.leaveApprover) {
			await this.fillLink('leave_approver', options.leaveApprover);
		}
	}

	async saveAndSubmit(): Promise<string> {
		await this.save();
		await this.submit({ allowConfirm: true });
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Leave Application name not found after submit');
		}
		return name;
	}

	async approve(): Promise<void> {
		await this.clickWorkflowAction('Approve');
	}

	async reject(): Promise<void> {
		await this.clickWorkflowAction('Reject');
	}

	async setStatus(status: 'Approved' | 'Rejected' | 'Open'): Promise<void> {
		await this.fillSelect('status', status);
		await this.save();
		if (status !== 'Open') {
			await this.submit();
		}
	}
}
