import { type Page, expect } from '@playwright/test';
import { ROUTES } from '../helpers/routes';

export class BudgetHealthPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto(ROUTES.budgetHealth);
		await this.page.waitForLoadState('networkidle');
	}

	heading() {
		return this.page.getByRole('heading', { name: 'Budget Health', level: 1 });
	}

	refreshButton() {
		return this.page.getByRole('button', { name: /Refresh|Loading/ });
	}

	async expectLoaded() {
		await expect(this.page).toHaveURL(/\/volunteering\/budget-health/);
		await expect(this.heading()).toBeVisible();
		await expect(this.page.locator('#app')).toBeVisible();
		// Table or empty state after load finishes
		await expect(this.refreshButton()).toBeEnabled({ timeout: 30000 });
	}
}
