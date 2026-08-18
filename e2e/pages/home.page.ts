import { type Page, expect } from '@playwright/test';
import { ROUTES } from '../helpers/routes';

export class HomePage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto(ROUTES.home);
		await this.page.waitForLoadState('networkidle');
	}

	heading() {
		return this.page.getByRole('heading', { level: 1 });
	}

	async expectLoaded() {
		await expect(this.page).toHaveURL(/\/volunteering\/home/);
		await expect(this.page.locator('#app')).toBeVisible();
		await expect(this.heading()).toBeVisible({ timeout: 30000 });
	}
}
