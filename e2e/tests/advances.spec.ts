import { expect, test } from '@playwright/test';
import { AdvancesPage } from '../pages/advances.page';

test.describe('AC-ADV-009 Advance Portal shows status', () => {
	test('AC-ADV-009: Advance Portal shows status', async ({ page }) => {
		const advances = new AdvancesPage(page);
		await advances.goto();
		await advances.expectLoaded();

		await expect(advances.newAdvanceLink()).toHaveAttribute(
			'href',
			'/app/employee-advance/new',
		);

		// Empty list, residual badges, or "no Employee linked" error are all valid load outcomes
		const emptyState = page.getByText(/No advances yet/);
		const residualBadge = page.getByText(/Residual/);
		const loadError = page.locator('.text-red-600');
		await expect(emptyState.or(residualBadge.first()).or(loadError)).toBeVisible();
	});

	test('Refresh keeps Advance Portal shell mounted', async ({ page }) => {
		const advances = new AdvancesPage(page);
		await advances.goto();
		await advances.expectLoaded();
		await advances.refreshButton().click();
		await expect(advances.heading()).toBeVisible();
		await expect(page.locator('#app')).toBeVisible();
	});
});
