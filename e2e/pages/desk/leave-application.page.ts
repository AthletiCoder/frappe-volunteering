import type { Page } from '@playwright/test';
import { resolvePostActionModal } from '../../helpers/dialogs';
import { DeskForm } from '../../helpers/desk';

export class LeaveApplicationFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Leave Application');
		await this.waitForEmployeeDefault();
	}

	private async waitForEmployeeDefault(): Promise<void> {
		await this.page.waitForFunction(
			() =>
				Boolean(
					(window as unknown as { cur_frm?: { doc?: { employee?: string } } }).cur_frm?.doc
						?.employee,
				),
			undefined,
			{ timeout: 15000 },
		);
	}

	async ensureLeaveApprover(explicit?: string): Promise<void> {
		if (explicit) {
			await this.setLeaveApprover(explicit);
		}
		await this.page.evaluate(async () => {
			const win = window as unknown as {
				cur_frm?: {
					doc?: { employee?: string; leave_approver?: string };
					set_value: (field: string, value: string) => Promise<void>;
				};
				frappe?: {
					db: {
						get_value: (
							doctype: string,
							name: string,
							field: string | string[],
						) => Promise<{ message?: Record<string, string> }>;
					};
				};
			};
			const frm = win.cur_frm;
			if (!frm?.doc?.employee || frm.doc.leave_approver) {
				return;
			}
			const employee = await win.frappe?.db.get_value('Employee', frm.doc.employee, [
				'leave_approver',
				'reports_to',
			]);
			let approver = employee?.message?.leave_approver;
			if (!approver && employee?.message?.reports_to) {
				const manager = await win.frappe?.db.get_value(
					'Employee',
					employee.message.reports_to,
					'user_id',
				);
				approver = manager?.message?.user_id;
			}
			if (approver) {
				await frm.set_value('leave_approver', approver);
				const fullName = await win.frappe?.db.get_value('User', approver, 'full_name');
				if (fullName?.message?.full_name) {
					await frm.set_value('leave_approver_name', fullName.message.full_name);
				}
			}
		});
		await this.page
			.waitForFunction(
				() =>
					Boolean(
						(window as unknown as { cur_frm?: { doc?: { leave_approver?: string } } }).cur_frm
							?.doc?.leave_approver,
					),
				undefined,
				{ timeout: 15000 },
			)
			.catch(() => {});
	}

	async open(name: string): Promise<void> {
		await this.gotoForm('Leave Application', name);
	}

	async setEmployee(employeeId: string): Promise<void> {
		try {
			await this.fillLink('employee', employeeId);
		} catch {
			await this.page.evaluate((emp) => {
				const frm = (window as unknown as { cur_frm?: { set_value: (f: string, v: string) => void } })
					.cur_frm;
				frm?.set_value('employee', emp);
			}, employeeId);
		}
	}

	async saveDraft(): Promise<string> {
		await this.ensureLeaveApprover();
		const saveWait = this.waitForSaveResponse('Leave Application');
		await this.save();
		const savedDoc = await saveWait.catch(() => null);
		if (savedDoc?.name) {
			return savedDoc.name;
		}
		return this.waitForPersistedDocName();
	}

	async setLeaveApprover(approverEmail: string): Promise<void> {
		try {
			await this.fillLink('leave_approver', approverEmail);
		} catch {
			await this.page.evaluate(async (email) => {
				const frm = (window as unknown as {
					cur_frm?: { set_value: (f: string, v: string) => Promise<void> };
				}).cur_frm;
				await frm?.set_value('leave_approver', email);
				const fullName = await (
					window as unknown as {
						frappe: { db: { get_value: (d: string, n: string, f: string) => Promise<{ message?: { full_name?: string } }> } };
					}
				).frappe.db.get_value('User', email, 'full_name');
				if (fullName?.message?.full_name) {
					await frm?.set_value('leave_approver_name', fullName.message.full_name);
				}
			}, approverEmail);
		}
		await this.page
			.waitForFunction(
				(email) =>
					(window as unknown as { cur_frm?: { doc?: { leave_approver?: string } } }).cur_frm?.doc
						?.leave_approver === email,
				approverEmail,
				{ timeout: 10000 },
			)
			.catch(() => {});
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
			await this.setLeaveApprover(options.leaveApprover);
		} else {
			await this.ensureLeaveApprover();
		}
	}

	/** Employee path: save draft (Open). Manager submits separately. */
	async saveAndSubmit(): Promise<string> {
		const name = await this.saveDraft();
		const submitBtn = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: /^Submit$/ })
			.first();
		if (await submitBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
			await submitBtn.click();
			await resolvePostActionModal(this.page, { allowConfirm: true });
		}
		return this.getDocNameFromUrl() || name;
	}

	async approve(): Promise<void> {
		await this.clickWorkflowAction('Approve');
	}

	async reject(): Promise<void> {
		await this.clickWorkflowAction('Reject');
	}

	async setStatus(
		status: 'Approved' | 'Rejected' | 'Open',
		options?: { expectError?: RegExp | string },
	): Promise<void> {
		await this.fillSelect('status', status);
		await this.save(options?.expectError ? { expectError: options.expectError } : undefined);
		if (status === 'Open' || options?.expectError) {
			if (options?.expectError) {
				await this.submit({ expectError: options.expectError });
			}
			return;
		}
		await this.submit();
	}
}
