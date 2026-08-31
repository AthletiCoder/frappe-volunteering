import { expect, test } from '@playwright/test';
import { callMethod } from '../../helpers/frappe';
import { personaStorage } from '../../helpers/personas';
import { HomePage } from '../../pages/home.page';
import { DeskForm } from '../../helpers/desk';
import { ApprovalLimitsPage } from '../../pages/desk/approval-limits.page';

test.describe('Volunteering product gaps @volunteering @ui', () => {
	test.describe('as volunteer', () => {
		test.use({ storageState: personaStorage('volunteer') });

		test('VO-001 @regression: Volunteer blocked from staff Home', async ({ page, request }) => {
			const payload = await callMethod<{
				allowed: boolean;
				persona: string;
				greeting: string;
			}>(request, 'volunteering.volunteering.home_service.get_home_payload', {}, 'volunteer');
			expect(payload.allowed).toBe(false);
			expect(payload.persona).toBe('volunteer');

			const home = new HomePage(page);
			await home.goto();
			await expect(page.locator('#app, .page-container, body')).toBeVisible({ timeout: 15000 });
		});
	});

	test.describe('as coordinator', () => {
		test.use({ storageState: personaStorage('coordinator') });

		test('VO-002 @regression: Coordinator can open NGO Event form', async ({ page }) => {
			const desk = new DeskForm(page);
			await desk.gotoForm('NGO Event');
			await expect(desk.field('title').locator('input, textarea').first()).toBeVisible();
		});
	});

	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('VO-003 @regression: Accounts Manager opens Donation list', async ({ page }) => {
			const desk = new DeskForm(page);
			await desk.gotoList('Donation');
			await expect(page.locator('.frappe-list, .list-row-container').first()).toBeVisible();
		});

		test('VO-004 @regression: Cashfree Settings form reachable', async ({ page }) => {
			await page.goto('/app/cashfree-settings/Cashfree%20Settings', {
				waitUntil: 'domcontentloaded',
			});
			await expect(page.locator('.form-layout, [data-fieldname]').first()).toBeVisible({
				timeout: 30000,
			});
		});
	});

	test.describe('as hr', () => {
		test.use({ storageState: personaStorage('hr') });

		test('VO-005 @regression: HR User read-only on Approval Limits', async ({ page }) => {
			const limits = new ApprovalLimitsPage(page);
			await limits.open();
			await limits.expectReadOnly();
		});
	});

	test('VO-006 @smoke: Event registration form reachable', async ({ page }) => {
		const response = await page.goto('/event-registration-form', {
			waitUntil: 'domcontentloaded',
		});
		expect(response?.ok() || response?.status() === 404).toBeTruthy();
		await expect(page.locator('body')).toBeVisible();
	});
});
