import { expect, test } from '@playwright/test';
import { AdvancesPage } from '../../pages/advances.page';
import { BudgetHealthPage } from '../../pages/budget-health.page';
import { HomePage } from '../../pages/home.page';
import { personaStorage } from '../../helpers/personas';

test.describe('Accounts L1 smoke @smoke @accounts', () => {
	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-BUD-004: Budget Health page loads', async ({ page }) => {
			const budgetHealth = new BudgetHealthPage(page);
			await budgetHealth.goto();
			await budgetHealth.expectLoaded();
			await expect(page.getByRole('columnheader', { name: 'Project' })).toBeVisible();
		});

		test('Budget Health nav to Advances works', async ({ page }) => {
			const budgetHealth = new BudgetHealthPage(page);
			await budgetHealth.goto();
			await page.getByRole('link', { name: 'Advances' }).first().click();
			await expect(page).toHaveURL(/\/volunteering\/advances/);
			await expect(
				page.getByRole('heading', { name: 'Advance Portal', level: 1 }),
			).toBeVisible();
		});

		test('AC-HOME-001: Accounts Home shows pay queues or empty Home', async ({ page }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
			await expect(page.getByRole('link', { name: 'Home' }).first()).toBeVisible();
		});
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-ADV-009: Advance Portal shows status', async ({ page }) => {
			const advances = new AdvancesPage(page);
			await advances.goto();
			await advances.expectLoaded();
			const emptyState = page.getByText(/No advances yet/);
			const residualBadge = page.getByText(/Residual/);
			const loadError = page.locator('.text-bad');
			await expect(emptyState.or(residualBadge.first()).or(loadError)).toBeVisible();
		});

		test('AC-BKS-003: Home loads for employee spend actions', async ({ page }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
			await expect(page.getByRole('link', { name: 'Claim money back' })).toBeVisible();
			await expect(page.getByRole('link', { name: 'Request an advance' })).toBeVisible();
			await expect(page.getByText('To pay')).toHaveCount(0);
		});
	});
});
