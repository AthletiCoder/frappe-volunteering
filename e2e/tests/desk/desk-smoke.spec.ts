import { expect, test } from '@playwright/test';
import { DESK_WORKSPACE_RE, ROUTES } from '../../helpers/routes';

/**
 * Wave 2 Desk stubs. Run with: yarn test:e2e --grep @desk
 * Expand using spreadsheet P0 IDs (HR-DWL-*, AC-ADV-*, etc.).
 */
test.describe('Desk smoke @desk', () => {
	test('My Work workspace loads', async ({ page }) => {
		await page.goto(ROUTES.myWork);
		await page.waitForLoadState('networkidle');
		await expect(page).toHaveURL(DESK_WORKSPACE_RE.myWork);
		await expect(page.locator('body')).not.toHaveClass(/login-page/);
		await expect(
			page.locator('.layout-main, .page-container, #body, .desk-sidebar').first(),
		).toBeVisible({
			timeout: 30000,
		});
	});

	test('My Expenses workspace loads', async ({ page }) => {
		await page.goto(ROUTES.myExpenses);
		await page.waitForLoadState('networkidle');
		await expect(page).toHaveURL(DESK_WORKSPACE_RE.myExpenses);
		await expect(
			page.locator('.layout-main, .page-container, #body, .desk-sidebar').first(),
		).toBeVisible({
			timeout: 30000,
		});
	});
});
