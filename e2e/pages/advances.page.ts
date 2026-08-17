import { type Page, expect } from '@playwright/test';
import { ROUTES } from '../helpers/routes';

export class AdvancesPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto(ROUTES.advances);
		await this.page.waitForLoadState('networkidle');
	}

	heading() {
		return this.page.getByRole('heading', { name: 'Advance Portal', level: 1 });
	}

	refreshButton() {
		return this.page.getByRole('button', { name: 'Refresh' });
	}

	newAdvanceLink() {
		return this.page.getByRole('link', { name: 'New Advance' });
	}

	async expectLoaded() {
		await expect(this.page).toHaveURL(/\/volunteering\/advances/);
		await expect(this.heading()).toBeVisible();
		await expect(this.page.locator('#app')).toBeVisible();
		await expect(this.refreshButton()).toBeVisible({ timeout: 30000 });
	}
}
