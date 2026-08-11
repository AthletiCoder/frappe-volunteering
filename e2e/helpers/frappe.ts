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
			...csrfHeaders(persona),
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
				...csrfHeaders(persona),
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
				...csrfHeaders(persona),
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
	request: APIRequestContext,
	method: string,
	args: Record<string, unknown> = {},
	persona: PersonaKey = DEFAULT_PERSONA,
): Promise<T> {
	const response = await request.post(`/api/method/${method}`, {
		data: args,
		headers: {
			'Content-Type': 'application/json',
			...csrfHeaders(persona),
		},
	});

	if (!response.ok()) {
		throw new Error(`Failed to call ${method}: ${await response.text()}`);
	}

	const result: FrappeResponse<T> = await response.json();
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
