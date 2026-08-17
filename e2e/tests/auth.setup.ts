import * as fs from 'fs';
import { expect, test as setup } from '@playwright/test';
import { ensureAuthDir } from '../helpers/frappe';
import {
	DEFAULT_PERSONA,
	type PersonaKey,
	PERSONAS,
} from '../helpers/personas';

// Authenticating all personas needs more than the default 60s.
setup.setTimeout(400_000);

/**
 * Authenticate every persona once; write storageState + CSRF per alias.
 */
setup('authenticate personas', async () => {
	ensureAuthDir();

	const keys = Object.keys(PERSONAS) as PersonaKey[];
	const reuseAuth =
		!process.env.E2E_FORCE_AUTH &&
		keys.every((key) => fs.existsSync(PERSONAS[key].storageState));
	if (reuseAuth) {
		console.log(
			'Reusing e2e/.auth sessions (set E2E_FORCE_AUTH=1 to log in again)',
		);
		return;
	}

	const { chromium } = await import('@playwright/test');
	const browser = await chromium.launch({
		channel: process.env.E2E_BROWSER_CHANNEL || 'chrome',
	});
	try {
	for (const key of keys) {
		const persona = PERSONAS[key];
		const context = await browser.newContext();
		const page = await context.newPage();

		const loginResponse = await page.request.post('/api/method/login', {
			form: {
				usr: persona.email,
				pwd: persona.password,
			},
		});
		expect(
			loginResponse.ok(),
			`Login failed for ${key} (${persona.email}): ${await loginResponse.text()}`,
		).toBeTruthy();

		const userResponse = await page.request.get(
			'/api/method/frappe.auth.get_logged_user',
		);
		expect(userResponse.ok()).toBeTruthy();
		const userData = await userResponse.json();
		expect(userData.message).not.toBe('Guest');
		console.log(`Authenticated ${key} as: ${userData.message}`);

		// NGO Member has no Desk — land on site root. Staff use Desk for CSRF.
		const landing = key === 'volunteer' ? '/' : '/desk';
		await page.goto(landing, { waitUntil: 'domcontentloaded' });
		let csrfToken: string | undefined;
		try {
			csrfToken = await page.waitForFunction(
				() =>
					(window as unknown as { frappe?: { csrf_token?: string } }).frappe
						?.csrf_token || '',
				{ timeout: 20000 },
			).then((h) => h.jsonValue() as Promise<string>);
		} catch {
			const cookies = await context.cookies();
			csrfToken = cookies.find((c) => c.name === 'csrf_token')?.value;
		}

		if (csrfToken) {
			fs.writeFileSync(
				persona.csrfFile,
				JSON.stringify({ csrf_token: csrfToken }),
			);
		}

		await context.storageState({ path: persona.storageState });
		await context.close();
	}

	const adminState = PERSONAS[DEFAULT_PERSONA].storageState;
	if (fs.existsSync(adminState)) {
		fs.copyFileSync(adminState, 'e2e/.auth/user.json');
	}
	const adminCsrf = PERSONAS[DEFAULT_PERSONA].csrfFile;
	if (fs.existsSync(adminCsrf)) {
		fs.copyFileSync(adminCsrf, 'e2e/.auth/csrf.json');
	}
	} finally {
		await browser.close();
	}
});
