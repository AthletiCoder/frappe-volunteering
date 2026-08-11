import { type Page, expect } from '@playwright/test';
import { ROUTES } from '../helpers/routes';

export class LoginPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto(ROUTES.login);
		await this.page.waitForLoadState('networkidle');
	}

	async login(
		email = process.env.FRAPPE_USER || 'Administrator',
		password = process.env.FRAPPE_PASSWORD || 'password',
	) {
		await this.goto();
		await this.page.locator('#login_email, input[data-fieldname="email"]').first().fill(email);
		await this.page
			.locator('#login_password, input[data-fieldname="password"]')
			.first()
			.fill(password);
		await this.page.locator('button.btn-login, button[type="submit"]').first().click();
		await this.page.waitForURL(/\/(app|desk|volunteering)/, { timeout: 30000 });
	}

	async expectToBeOnLoginPage() {
		await expect(this.page).toHaveURL(/.*login.*/);
	}
}
