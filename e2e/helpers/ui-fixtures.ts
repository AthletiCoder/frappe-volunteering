import type { APIRequestContext } from '@playwright/test';
import { e2eCall, getFixtures } from './e2e-api';

let cachedProject: string | null = null;
let cachedMasters: {
	project: string;
	project_name: string;
	supplier_name: string;
	item_code: string;
	expense_type: string;
} | null = null;

/** E2E project id for link fields in Desk forms. */
export async function getE2eProject(request: APIRequestContext): Promise<string> {
	if (cachedProject) {
		return cachedProject;
	}
	const fixtures = await getFixtures(request, 'admin');
	cachedProject = fixtures.project;
	return cachedProject;
}

export async function getE2eMasters(request: APIRequestContext) {
	if (cachedMasters) {
		return cachedMasters;
	}
	cachedMasters = await e2eCall(request, 'get_masters', {}, 'admin');
	if (!cachedMasters) {
		throw new Error('E2E get_masters returned empty');
	}
	return cachedMasters;
}

/** Attach a test receipt to a draft claim (setup-only; not a user-facing action). */
export async function attachClaimReceipt(
	request: APIRequestContext,
	claimName: string,
): Promise<void> {
	await e2eCall(request, 'attach_claim_receipt', { name: claimName }, 'admin');
}
