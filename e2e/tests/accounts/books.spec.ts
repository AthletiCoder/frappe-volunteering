import { expect, test } from '@playwright/test';
import { e2eCall } from '../../helpers/e2e-api';
import { personaStorage } from '../../helpers/personas';
import { DeskForm } from '../../helpers/desk';

test.describe('Books and hubs @accounts @ui', () => {
	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-BKS-001 @regression: Cashfree clearing Journal Entry form reachable', async ({
			page,
		}) => {
			const desk = new DeskForm(page);
			await desk.gotoForm('Journal Entry');
			await expect(page.locator('.form-layout:visible, .form-page:visible').first()).toBeVisible();
			await expect(
				page.locator('[data-fieldname="voucher_type"], [data-fieldname="company"]').first(),
			).toBeVisible();
		});

		test('AC-BKS-002 @regression: Cancel preserves history (submitted doc not deletable)', async ({
			page,
		}) => {
			const desk = new DeskForm(page);
			await desk.gotoList('Payment Entry');
			await expect(page.locator('.list-row, .frappe-list, .no-result').first()).toBeVisible();
			const firstRow = page.locator('.list-row').first();
			if (await firstRow.isVisible().catch(() => false)) {
				await firstRow.click();
				await desk.waitForFormReady();
				const deleteBtn = page.locator('button, .dropdown-item').filter({ hasText: /^Delete$/ });
				await expect(deleteBtn).toHaveCount(0);
			}
		});

		test('AC-BKS-004 @regression: General Ledger report runs', async ({ page }) => {
			const desk = new DeskForm(page);
			await desk.gotoReport('General Ledger');
			await expect(page.locator('.report-wrapper, .query-report')).toBeVisible();
			await expect(page.locator('.report-wrapper .dt-scrollable, .report-wrapper .report-table').first()).toBeVisible();
		});

		test('AC-BKS-005 @regression: Bank Reconciliation Tool opens', async ({ page, request }) => {
			const allowed = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Bank Reconciliation Tool', ptype: 'read' },
				'accounts',
			);
			await page.goto('/desk/bank-reconciliation-tool', { waitUntil: 'domcontentloaded' });
			const desk = new DeskForm(page);
			await desk.dismissBlockingModals();
			if (allowed) {
				await expect(
					page.locator('[data-fieldname="company"], .bank-reconciliation-tool').first(),
				).toBeVisible({ timeout: 45000 });
				return;
			}
			await expect(page.getByText(/not permitted|No permission/i).first()).toBeVisible({
				timeout: 45000,
			});
		});
	});
});
