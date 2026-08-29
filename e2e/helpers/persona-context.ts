import type { Browser, Page } from '@playwright/test';
import { personaStorage, type PersonaKey } from './personas';

/** Run a block with a specific persona's browser session (multi-actor UI tests). */
export async function withPersona(
	browser: Browser,
	persona: PersonaKey,
	fn: (page: Page) => Promise<void>,
): Promise<void> {
	const context = await browser.newContext({ storageState: personaStorage(persona) });
	const page = await context.newPage();
	try {
		await fn(page);
	} finally {
		await context.close();
	}
}
