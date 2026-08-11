import type { APIRequestContext, Page } from '@playwright/test';

/**
 * Login via Frappe API (faster than UI login).
 */
export async function loginViaAPI(
	request: APIRequestContext,
	email = process.env.FRAPPE_USER || 'Administrator',
	password = process.env.FRAPPE_PASSWORD || 'password',
): Promise<void> {
	const response = await request.post('/api/method/login', {
		form: {
			usr: email,
			pwd: password,
		},
	});

	if (!response.ok()) {
		throw new Error(
			`Login failed: ${response.status()} ${await response.text()}`,
		);
	}
}

/**
 * Login via UI (for testing the login flow itself).
 */
export async function loginViaUI(
	page: Page,
	email = process.env.FRAPPE_USER || 'Administrator',
	password = process.env.FRAPPE_PASSWORD || 'password',
): Promise<void> {
	await page.goto('/login');
	await page.waitForLoadState('networkidle');

	const emailInput = page.locator('#login_email, input[data-fieldname="email"]').first();
	const passwordInput = page.locator('#login_password, input[data-fieldname="password"]').first();
	await emailInput.fill(email);
	await passwordInput.fill(password);
	await page.locator('button.btn-login, button[type="submit"]').first().click();

	await page.waitForURL(/\/(app|desk|volunteering)/, { timeout: 30000 });
}

/**
 * Logout the current user.
 */
export async function logout(page: Page): Promise<void> {
	await page.goto('/api/method/logout');
	await page.waitForLoadState('networkidle');
}

/**
 * Check if user is logged in by verifying session.
 */
export async function isLoggedIn(request: APIRequestContext): Promise<boolean> {
	try {
		const response = await request.get(
			'/api/method/frappe.auth.get_logged_user',
		);
		if (!response.ok()) return false;

		const data = await response.json();
		return Boolean(data.message && data.message !== 'Guest');
	} catch {
		return false;
	}
}
