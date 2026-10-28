import { expect, request as requestFactory, test } from '@playwright/test';
import { PERSONAS } from '../../helpers/personas';
import { loginViaAPI } from '../../helpers/auth';
import { requireLocalRegression } from '../../helpers/portal-regression';

test('two devices can sign in as the same employee without session-update server errors', async ({ baseURL }, testInfo) => {
	requireLocalRegression(baseURL);
	const admin = await requestFactory.newContext({ baseURL });
	await loginViaAPI(admin, PERSONAS.admin.email, PERSONAS.admin.password);
	const lastLogin = async () => {
		const result = await admin.get('/api/method/frappe.client.get_value', {
			params: { doctype: 'User', filters: JSON.stringify({ name: PERSONAS.employee.email }), fieldname: 'last_login' },
		});
		expect(result.status()).toBe(200);
		return (await result.json()).message.last_login;
	};
	const before = await lastLogin();
	const observations: { round: number; device: number; status: number; error?: string }[] = [];
	for (let round = 0; round < 10; round++) {
		const clients = await Promise.all([requestFactory.newContext({ baseURL }), requestFactory.newContext({ baseURL })]);
		try {
			await Promise.all(clients.map(async (client, device) => {
				const response = await client.post('/api/method/login', {
					form: { usr: PERSONAS.employee.email, pwd: PERSONAS.employee.password },
				});
				const observation = { round, device, status: response.status(), ...(!response.ok() ? { error: (await response.text()).slice(0, 500) } : {}) };
				observations.push(observation);
				if (response.ok()) {
					const identity = await client.get('/api/method/frappe.auth.get_logged_user');
					expect((await identity.json()).message).toBe(PERSONAS.employee.email);
				}
			}));
		} finally { await Promise.all(clients.map(client => client.dispose())); }
	}
	await testInfo.attach('parallel-login-statuses', { body: JSON.stringify(observations, null, 2), contentType: 'application/json' });
	// A fix must persist activity metadata, not just silence every update.
	const after = await lastLogin();
	await admin.dispose();
	expect(after).toBeTruthy();
	expect(after).not.toBe(before);
	expect(observations.filter(row => row.status !== 200), 'Every correct two-device login must succeed, including session metadata updates').toEqual([]);
});

test('incorrect password remains rejected and does not create an authenticated session', async ({ request, baseURL }) => {
	requireLocalRegression(baseURL);
	const rejected = await request.post('/api/method/login', {
		form: { usr: PERSONAS.employee.email, pwd: 'deliberately-incorrect-qa-password' },
	});
	expect(rejected.status()).toBe(401);
	const identity = await request.get('/api/method/frappe.auth.get_logged_user');
	expect([401, 403]).toContain(identity.status());
});
