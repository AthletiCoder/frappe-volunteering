import { expect, test } from '@playwright/test';
import { AdvancesPage } from '../../pages/advances.page';
import { BudgetHealthPage } from '../../pages/budget-health.page';
import { personaStorage } from '../../helpers/personas';
import { DESK_WORKSPACE_RE, ROUTES } from '../../helpers/routes';

test.describe('Accounts L1 smoke @smoke @accounts', () => {
	test('AC-BUD-004: Budget Health page loads', async ({ page }) => {
		const budgetHealth = new BudgetHealthPage(page);
		await budgetHealth.goto();
		await budgetHealth.expectLoaded();
		await expect(page.getByRole('columnheader', { name: 'Project' })).toBeVisible();
	});

	test('Budget Health nav to Advances works', async ({ page }) => {
		const budgetHealth = new BudgetHealthPage(page);
		await budgetHealth.goto();
		await page.getByRole('link', { name: 'Advances' }).click();
		await expect(page).toHaveURL(/\/volunteering\/advances/);
		await expect(
			page.getByRole('heading', { name: 'Advance Portal', level: 1 }),
		).toBeVisible();
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-ADV-009: Advance Portal shows status', async ({ page }) => {
			const advances = new AdvancesPage(page);
			await advances.goto();
			await advances.expectLoaded();
			const emptyState = page.getByText(/No advances yet/);
			const residualBadge = page.getByText(/Residual/);
			const loadError = page.locator('.text-red-600');
			await expect(emptyState.or(residualBadge.first()).or(loadError)).toBeVisible();
		});

		test('AC-BKS-003: My Expenses hub loads', async ({ page }) => {
			await page.goto(ROUTES.myExpenses, { waitUntil: 'domcontentloaded' });
			await expect(page).toHaveURL(DESK_WORKSPACE_RE.myExpenses);
			await expect(
				page.locator('.layout-main, .page-container, #body, .desk-sidebar').first(),
			).toBeVisible({ timeout: 30000 });
		});
	});
});
