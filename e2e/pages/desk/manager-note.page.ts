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
		await this.fillLink('employee', options.employee);
		await this.fillSelect('note_type', options.noteType);
		await this.fillData('content', options.content);
		await this.save();
		const name = this.getDocNameFromUrl();
		if (!name) {
			throw new Error('Manager Note name not found after save');
		}
		return name;
	}
}
