import type { Page } from '@playwright/test';
import { DeskForm } from '../../helpers/desk';

export class ManagerNoteFormPage extends DeskForm {
	constructor(page: Page) {
		super(page);
	}

	async openNew(): Promise<void> {
		await this.gotoForm('Manager Note');
	}

	async createNote(options: {
		employee: string;
		noteType: string;
		content: string;
	}): Promise<string> {
		const name = await this.page.evaluate(
			async ({ employee, noteType, content }) => {
				const result = await (
					window as unknown as {
						frappe: {
							call: (opts: {
								method: string;
								args: Record<string, unknown>;
							}) => Promise<{ message?: { name?: string } }>;
							set_route: (type: string, doctype: string, docname: string) => void;
						};
					}
				).frappe.call({
					method: 'frappe.client.insert',
					args: {
						doc: {
							doctype: 'Manager Note',
							employee,
							note_type: noteType,
							content,
						},
					},
				});
				const docname = result.message?.name;
				if (!docname) {
					throw new Error('Manager Note insert failed');
				}
				(
					window as unknown as {
						frappe: { set_route: (type: string, doctype: string, docname: string) => void };
					}
				).frappe.set_route('Form', 'Manager Note', docname);
				return docname;
			},
			options,
		);
		await this.waitForFormReady();
		return name;
	}
}
