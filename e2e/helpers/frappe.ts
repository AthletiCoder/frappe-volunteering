import * as fs from 'fs';
import * as path from 'path';
import type { APIRequestContext } from '@playwright/test';
import { DEFAULT_PERSONA, type PersonaKey, PERSONAS } from './personas';

export interface FrappeResponse<T = unknown> {
	message?: T;
	exc?: string;
	exc_type?: string;
	_server_messages?: string;
}

const csrfCache = new Map<string, string>();

function apiBaseUrl(): string {
	return process.env.BASE_URL || 'http://sevamrita.local:8000';
}

/** Drop cached CSRF after auth.setup rewrites e2e/.auth (optional persona). */
export function clearPersonaCsrfCache(persona?: PersonaKey): void {
	if (persona) {
		csrfCache.delete(persona);
		return;
	}
	csrfCache.clear();
}

function personaCookieHeader(persona: PersonaKey = DEFAULT_PERSONA): Record<string, string> {
	try {
		const statePath = PERSONAS[persona].storageState;
		if (!fs.existsSync(statePath)) {
			return {};
		}
		const state = JSON.parse(fs.readFileSync(statePath, 'utf-8')) as {
			cookies?: Array<{ name: string; value: string }>;
		};
		const cookies = state.cookies || [];
		if (!cookies.length) {
			return {};
		}
		return {
			Cookie: cookies.map((c) => `${c.name}=${c.value}`).join('; '),
		};
	} catch (error) {
		console.warn(`Failed to read cookies for ${persona}:`, error);
		return {};
	}
}

function personaHeaders(persona: PersonaKey = DEFAULT_PERSONA): Record<string, string> {
	return {
		...personaCookieHeader(persona),
		...csrfHeaders(persona),
	};
}

function getCsrfToken(persona: PersonaKey = DEFAULT_PERSONA): string {
	if (csrfCache.has(persona)) {
		return csrfCache.get(persona) || '';
	}

	try {
		const csrfFile = PERSONAS[persona].csrfFile;
		if (fs.existsSync(csrfFile)) {
			const data = JSON.parse(fs.readFileSync(csrfFile, 'utf-8'));
			const token = data.csrf_token || '';
			csrfCache.set(persona, token);
			return token;
		}
	} catch (error) {
		console.warn(`Failed to read CSRF for ${persona}:`, error);
	}

	csrfCache.set(persona, '');
	return '';
}

function csrfHeaders(persona: PersonaKey = DEFAULT_PERSONA): Record<string, string> {
	const csrfToken = getCsrfToken(persona);
	return csrfToken ? { 'X-Frappe-CSRF-Token': csrfToken } : {};
}

function isGuestApiResponse(body: string): boolean {
	return body.includes('"full_name":"Guest"') || body.includes('PermissionError');
}

function parseSetCookieHeader(header: string): { name: string; value: string } | null {
	const [pair] = header.split(';');
	if (!pair) {
		return null;
	}
	const eq = pair.indexOf('=');
	if (eq <= 0) {
		return null;
	}
	return { name: pair.slice(0, eq).trim(), value: pair.slice(eq + 1).trim() };
}

/** Re-login via API when e2e/.auth sessions expire; updates storageState + CSRF files. */
export async function refreshPersonaAuth(persona: PersonaKey = DEFAULT_PERSONA): Promise<void> {
	const creds = PERSONAS[persona];
	const loginResponse = await fetch(`${apiBaseUrl()}/api/method/login`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: new URLSearchParams({ usr: creds.email, pwd: creds.password }),
	});
	if (!loginResponse.ok) {
		throw new Error(`Login failed for ${persona}: ${await loginResponse.text()}`);
	}

	const setCookies =
		typeof loginResponse.headers.getSetCookie === 'function'
			? loginResponse.headers.getSetCookie()
			: [];
	const cookieMap = new Map<string, string>();
	for (const header of setCookies) {
		const parsed = parseSetCookieHeader(header);
		if (parsed) {
			cookieMap.set(parsed.name, parsed.value);
		}
	}
	const cookieHeader = [...cookieMap.entries()].map(([k, v]) => `${k}=${v}`).join('; ');

	const landing = persona === 'volunteer' ? '/' : '/desk';
	const deskResponse = await fetch(`${apiBaseUrl()}${landing}`, {
		headers: cookieHeader ? { Cookie: cookieHeader } : {},
	});
	const deskHtml = await deskResponse.text();
	const csrfMatch = deskHtml.match(/csrf_token\s*[:=]\s*["']([^"']+)["']/);
	const csrfToken = csrfMatch?.[1] || cookieMap.get('csrf_token') || '';

	const host = new URL(apiBaseUrl()).hostname;
	const cookies = [...cookieMap.entries()].map(([name, value]) => ({
		name,
		value,
		domain: host,
		path: '/',
		expires: -1,
		httpOnly: name === 'sid',
		secure: false,
		sameSite: 'Lax' as const,
	}));

	ensureAuthDir();
	fs.writeFileSync(creds.storageState, JSON.stringify({ cookies }, null, 2));
	if (csrfToken) {
		fs.writeFileSync(creds.csrfFile, JSON.stringify({ csrf_token: csrfToken }));
	}
	clearPersonaCsrfCache(persona);

	if (persona === DEFAULT_PERSONA) {
		fs.copyFileSync(creds.storageState, path.join(path.dirname(creds.storageState), 'user.json'));
		if (csrfToken) {
			fs.copyFileSync(creds.csrfFile, path.join(path.dirname(creds.csrfFile), 'csrf.json'));
		}
	}
}

export async function createDoc<T = Record<string, unknown>>(
	request: APIRequestContext,
	doctype: string,
	doc: Record<string, unknown>,
	persona: PersonaKey = DEFAULT_PERSONA,
): Promise<T> {
	const response = await request.post(`/api/resource/${doctype}`, {
		data: doc,
		headers: {
			'Content-Type': 'application/json',
			...personaHeaders(persona),
		},
	});

	if (!response.ok()) {
		throw new Error(`Failed to create ${doctype}: ${await response.text()}`);
	}

	const result = await response.json();
	return result.data as T;
}

export async function getDoc<T = Record<string, unknown>>(
	request: APIRequestContext,
	doctype: string,
	name: string,
): Promise<T> {
	const response = await request.get(
		`/api/resource/${doctype}/${encodeURIComponent(name)}`,
	);

	if (!response.ok()) {
		throw new Error(
			`Failed to get ${doctype}/${name}: ${await response.text()}`,
		);
	}

	const result = await response.json();
	return result.data as T;
}

export async function updateDoc<T = Record<string, unknown>>(
	request: APIRequestContext,
	doctype: string,
	name: string,
	updates: Record<string, unknown>,
	persona: PersonaKey = DEFAULT_PERSONA,
): Promise<T> {
	const response = await request.put(
		`/api/resource/${doctype}/${encodeURIComponent(name)}`,
		{
			data: updates,
			headers: {
				'Content-Type': 'application/json',
				...personaHeaders(persona),
			},
		},
	);

	if (!response.ok()) {
		throw new Error(
			`Failed to update ${doctype}/${name}: ${await response.text()}`,
		);
	}

	const result = await response.json();
	return result.data as T;
}

export async function deleteDoc(
	request: APIRequestContext,
	doctype: string,
	name: string,
	persona: PersonaKey = DEFAULT_PERSONA,
): Promise<void> {
	const response = await request.delete(
		`/api/resource/${doctype}/${encodeURIComponent(name)}`,
		{
			headers: {
				...personaHeaders(persona),
			},
		},
	);

	if (!response.ok()) {
		throw new Error(
			`Failed to delete ${doctype}/${name}: ${await response.text()}`,
		);
	}
}

export async function callMethod<T = unknown>(
	_request: APIRequestContext,
	method: string,
	args: Record<string, unknown> = {},
	persona: PersonaKey = DEFAULT_PERSONA,
): Promise<T> {
	const invoke = async () => {
		const response = await fetch(`${apiBaseUrl()}/api/method/${method}`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				...personaHeaders(persona),
			},
			body: JSON.stringify(args),
		});
		const body = await response.text();
		return { response, body };
	};

	let { response, body } = await invoke();
	if (!response.ok || isGuestApiResponse(body)) {
		await refreshPersonaAuth(persona);
		({ response, body } = await invoke());
	}

	if (!response.ok) {
		throw new Error(`Failed to call ${method}: ${body}`);
	}

	const result: FrappeResponse<T> = JSON.parse(body);
	return result.message as T;
}

export async function getList<T = Record<string, unknown>>(
	request: APIRequestContext,
	doctype: string,
	options: {
		fields?: string[];
		filters?: Record<string, unknown> | unknown[];
		limit?: number;
		orderBy?: string;
	} = {},
): Promise<T[]> {
	const params = new URLSearchParams();

	if (options.fields) {
		params.set('fields', JSON.stringify(options.fields));
	}
	if (options.filters) {
		params.set('filters', JSON.stringify(options.filters));
	}
	if (options.limit !== undefined) {
		params.set('limit_page_length', options.limit.toString());
	}
	if (options.orderBy) {
		params.set('order_by', options.orderBy);
	}

	const response = await request.get(
		`/api/resource/${doctype}?${params.toString()}`,
	);

	if (!response.ok()) {
		throw new Error(`Failed to get list of ${doctype}: ${await response.text()}`);
	}

	const result = await response.json();
	return result.data as T[];
}

export async function docExists(
	request: APIRequestContext,
	doctype: string,
	name: string,
): Promise<boolean> {
	try {
		await getDoc(request, doctype, name);
		return true;
	} catch {
		return false;
	}
}

/** Ensure auth dir exists (used by setup). */
export function ensureAuthDir(): void {
	const dir = path.dirname(PERSONAS.admin.storageState);
	if (!fs.existsSync(dir)) {
		fs.mkdirSync(dir, { recursive: true });
	}
}
