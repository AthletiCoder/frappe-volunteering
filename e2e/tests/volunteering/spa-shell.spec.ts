import { expect, test } from '@playwright/test';
import { callMethod } from '../../helpers/frappe';
import { HomePage } from '../../pages/home.page';
import { personaStorage } from '../../helpers/personas';

test.describe('SPA shell @smoke @volunteering', () => {
	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('Home previous-request pills sit on new-request cards', async ({ page }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
			await expect(page.getByRole('link', { name: 'Previous leave' })).toBeVisible();
			await expect(page.getByRole('link', { name: 'Previous claims' })).toBeVisible();
			await expect(page.getByRole('link', { name: 'Previous work logs' })).toBeVisible();
		});

		test('Previous leave pill count matches get_home_payload', async ({ page, request }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
			const payload = await callMethod<{
				actions: { time: { id: string; pending?: number }[] };
			}>(request, 'volunteering.volunteering.home_service.get_home_payload', {}, 'employee');
			const leave = payload.actions.time.find((row) => row.id === 'leave');
			const pill = page.getByRole('link', { name: 'Previous leave' });
			await expect(pill).toHaveAttribute('href', '/app/leave-application');
			await expect(pill).toContainText(String(leave?.pending ?? 0));
		});

		test('header nav opens Advances and shows Waiting on Home', async ({ page }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
			const nav = page.getByRole('navigation', { name: 'Sections' });
			await expect(nav.getByRole('link', { name: 'Home' })).toBeVisible();
			await expect(nav.getByRole('link', { name: 'To-do' })).toHaveCount(0);
			await expect(nav.getByRole('link', { name: 'Advances' })).toBeVisible();
			await expect(nav.getByRole('link', { name: 'Budgets' })).toHaveCount(0);
			await expect(
				page.getByRole('heading', { name: /Waiting on you|You’re clear|You're clear/i, level: 2 }),
			).toBeVisible();
			await nav.getByRole('link', { name: 'Advances' }).click();
			await expect(page).toHaveURL(/\/volunteering\/advances/);
			await expect(page.getByRole('heading', { name: 'Advance Portal', level: 1 })).toBeVisible();
		});

		test('/todos opens Waiting workbench', async ({ page }) => {
			await page.goto('/volunteering/todos');
			await expect(page).toHaveURL(/\/volunteering\/todos/);
			await expect(page.getByRole('heading', { name: 'Waiting', level: 1 })).toBeVisible();
			await expect(page.getByRole('button', { name: /All/i })).toBeVisible();
		});

		test('theme toggle flips html.dark', async ({ page }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
			const before = await page.evaluate(() =>
				document.documentElement.classList.contains('dark'),
			);
			await page.getByRole('button', { name: 'Toggle colour theme' }).click();
			const after = await page.evaluate(() =>
				document.documentElement.classList.contains('dark'),
			);
			expect(after).toBe(!before);
		});
	});

	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('header nav includes Budgets', async ({ page }) => {
			const home = new HomePage(page);
			await home.goto();
			await home.expectLoaded();
			await page
				.getByRole('navigation', { name: 'Sections' })
				.getByRole('link', { name: 'Budgets' })
				.click();
			await expect(page).toHaveURL(/\/volunteering\/budget-health/);
			await expect(page.getByRole('heading', { name: 'Budget Health', level: 1 })).toBeVisible();
		});
	});
});
