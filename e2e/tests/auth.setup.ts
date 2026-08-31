import * as fs from 'fs';
import * as path from 'path';
import { expect, request as playwrightRequest, test as setup } from '@playwright/test';
import { ensureAuthDir } from '../helpers/frappe';
import {
	DEFAULT_PERSONA,
	type PersonaKey,
	PERSONAS,
	e2eAuthDir,
} from '../helpers/personas';

// Authenticating all personas needs more than the default 60s.
setup.setTimeout(400_000);

const BASE_URL = process.env.BASE_URL || 'http://sevamrita.local:8000';

/** Spot-check that reused storageState cookies are still logged-in (not Guest). */
async function reusedSessionsAreValid(keys: PersonaKey[]): Promise<boolean> {
	const sample: PersonaKey[] = ['admin', 'employee', 'accounts'].filter((k) =>
		keys.includes(k),
	) as PersonaKey[];
	for (const key of sample) {
		const statePath = PERSONAS[key].storageState;
		if (!fs.existsSync(statePath)) {
			return false;
		}
		const ctx = await playwrightRequest.newContext({
			baseURL: BASE_URL,
			storageState: statePath,
		});
		try {
			const res = await ctx.get('/api/method/frappe.auth.get_logged_user');
			if (!res.ok()) {
				return false;
			}
			const body = await res.json();
			if (!body.message || body.message === 'Guest') {
				console.log(`Stale auth for ${key} (got ${body.message || 'empty'}); re-login.`);
				return false;
			}
		} finally {
			await ctx.dispose();
		}
	}
	return true;
}

/**
 * Authenticate every persona once; write storageState + CSRF per alias.
 */
setup('authenticate personas', async () => {
	ensureAuthDir();

	const keys = Object.keys(PERSONAS) as PersonaKey[];
	const filesPresent = keys.every((key) => fs.existsSync(PERSONAS[key].storageState));
	const reuseAuth =
		!process.env.E2E_FORCE_AUTH && filesPresent && (await reusedSessionsAreValid(keys));
	if (reuseAuth) {
		console.log(
			`Reusing ${e2eAuthDir()} sessions (set E2E_FORCE_AUTH=1 to log in again)`,
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
				csrfToken = await page
					.waitForFunction(
						() =>
							(window as unknown as { frappe?: { csrf_token?: string } }).frappe
								?.csrf_token || '',
						{ timeout: 20000 },
					)
					.then((h) => h.jsonValue() as Promise<string>);
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

		const authDir = e2eAuthDir();
		const adminState = PERSONAS[DEFAULT_PERSONA].storageState;
		if (fs.existsSync(adminState)) {
			fs.copyFileSync(adminState, path.join(authDir, 'user.json'));
		}
		const adminCsrf = PERSONAS[DEFAULT_PERSONA].csrfFile;
		if (fs.existsSync(adminCsrf)) {
			fs.copyFileSync(adminCsrf, path.join(authDir, 'csrf.json'));
		}
	} finally {
		await browser.close();
	}
});
