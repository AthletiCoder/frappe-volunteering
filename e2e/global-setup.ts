import './playwright-env';
import * as fs from 'fs';
import * as path from 'path';
import { request, type FullConfig } from '@playwright/test';
import { PERSONAS } from './helpers/personas';

const FIXTURES_FILE = path.join('e2e', '.fixtures.json');

/**
 * Seed E2E personas + project once per test run (not per spec file).
 * Uses the API request context only — no browser binary required.
 */
export default async function globalSetup(_config: FullConfig): Promise<void> {
	const baseURL = process.env.BASE_URL || 'http://sevamrita.local:8000';
	const admin = PERSONAS.admin;
	const context = await request.newContext({ baseURL });

	try {
		const login = await context.post('/api/method/login', {
			form: { usr: admin.email, pwd: admin.password },
		});
		if (!login.ok()) {
			throw new Error(
				`E2E globalSetup login failed: ${login.status()} ${await login.text()}`,
			);
		}

		const state = await context.storageState();
		const csrf =
			state.cookies.find((c) => c.name === 'csrf_token')?.value ||
			state.cookies.find((c) => c.name === 'sid')?.value ||
			'';

		const fixtures = await context.post(
			'/api/method/volunteering.volunteering.e2e_api.ensure_fixtures',
			{
				data: {},
				headers: {
					'Content-Type': 'application/json',
					...(csrf ? { 'X-Frappe-CSRF-Token': csrf } : {}),
				},
				timeout: 180_000,
			},
		);
		if (!fixtures.ok()) {
			throw new Error(
				`E2E globalSetup ensure_fixtures failed: ${await fixtures.text()}`,
			);
		}

		const body = (await fixtures.json()) as {
			message?: { project: string; department: string };
		};
		const message = body.message;
		if (!message?.project) {
			throw new Error('E2E globalSetup: ensure_fixtures returned no project');
		}

		fs.mkdirSync(path.dirname(FIXTURES_FILE), { recursive: true });
		fs.writeFileSync(FIXTURES_FILE, JSON.stringify(message, null, 2));
		console.log(`E2E fixtures ready: project=${message.project}`);
	} finally {
		await context.dispose();
	}
}
