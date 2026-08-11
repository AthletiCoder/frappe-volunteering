import { expect, test } from '@playwright/test';
import { BudgetHealthPage } from '../pages/budget-health.page';

test.describe('AC-BUD-004 Budget Health page loads', () => {
	test('AC-BUD-004: Budget Health page loads', async ({ page }) => {
		const budgetHealth = new BudgetHealthPage(page);
		await budgetHealth.goto();
		await budgetHealth.expectLoaded();

		// Table shell is always present; empty state cell may also show
		await expect(page.getByRole('columnheader', { name: 'Project' })).toBeVisible();
	});

	test('nav link Advances works from Budget Health', async ({ page }) => {
		const budgetHealth = new BudgetHealthPage(page);
		await budgetHealth.goto();
		await page.getByRole('link', { name: 'Advances' }).click();
		await expect(page).toHaveURL(/\/volunteering\/advances/);
		await expect(
			page.getByRole('heading', { name: 'Advance Portal', level: 1 }),
		).toBeVisible();
	});
});
