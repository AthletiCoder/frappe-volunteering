import { expect, type Page } from '@playwright/test';

/** Visible Frappe modal (msgprint / confirm / permission). */
export function modal(page: Page) {
	return page.locator('.modal.show .modal-dialog, .modal.fade.show .modal-dialog').last();
}

export type DeskModalKind = 'warning' | 'error' | 'permission' | 'confirm' | 'info' | 'unknown';

export interface DeskModalContent {
	visible: boolean;
	title: string;
	body: string;
	kind: DeskModalKind;
}

const WARNING_BODY =
	/below|minimum|low hours|leftover|residual|replenish|budget|vendor|threshold|prefer vendor|recommended|orange/i;
const ERROR_BODY =
	/mandatory|required|cannot|not allowed|blocked|invalid|exceed|overspend|duplicate|already exists/i;
const PERMISSION_TITLE = /permission error/i;
const PERMISSION_BODY = /insufficient permission/i;

export function classifyModal(title: string, body: string): DeskModalKind {
	if (PERMISSION_TITLE.test(title) || PERMISSION_BODY.test(body)) {
		return 'permission';
	}
	if (/low hours/i.test(title) || WARNING_BODY.test(body) || /warning/i.test(title)) {
		return 'warning';
	}
	if (ERROR_BODY.test(body) || /error/i.test(title)) {
		return 'error';
	}
	if (/confirm/i.test(title)) {
		return 'confirm';
	}
	if (body.trim()) {
		return 'info';
	}
	return 'unknown';
}

/** Read the topmost visible Desk modal without dismissing it. */
export async function readVisibleModal(page: Page): Promise<DeskModalContent> {
	const dialog = modal(page);
	const visible = await dialog.isVisible().catch(() => false);
	if (!visible) {
		return { visible: false, title: '', body: '', kind: 'unknown' };
	}
	const title = ((await dialog.locator('.modal-title').first().textContent()) || '').trim();
	const bodyEl = dialog.locator('.modal-body, .msgprint').first();
	let body = ((await bodyEl.textContent().catch(() => '')) || '').trim();
	if (!body) {
		body = ((await dialog.locator('.modal-content').textContent()) || '').replace(title, '').trim();
	}
	return { visible: true, title, body, kind: classifyModal(title, body) };
}

/** Click the primary / OK button on the visible modal. */
export async function dismissVisibleModal(page: Page): Promise<void> {
	const dialog = modal(page);
	if (!(await dialog.isVisible().catch(() => false))) {
		return;
	}
	const primary = dialog.locator(
		'.btn-primary, button.btn-modal-primary, .standard-actions .btn-primary',
	);
	if (await primary.first().isVisible().catch(() => false)) {
		await primary.first().click();
	} else {
		const closeBtn = dialog.locator('.modal-header button, button.close').last();
		if (await closeBtn.isVisible().catch(() => false)) {
			await closeBtn.click();
		} else {
			await dialog.getByRole('button').first().click();
		}
	}
	await dialog.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
}

/**
 * Known incidental permission dialog when hidden Account link fields load for
 * non-Accounts users (Employee Advance). Real users dismiss and continue.
 */
export async function dismissIncidentalPermissionModal(page: Page): Promise<DeskModalContent | null> {
	const content = await readVisibleModal(page);
	if (!content.visible) {
		return null;
	}
	if (content.kind === 'permission' && /account/i.test(content.body)) {
		await dismissVisibleModal(page);
		return content;
	}
	return null;
}

const ADVISORY_MODAL =
	/invoice split|split procurement|budget warning|budget exceeded|prefer vendor|emergency purchase|how to spend/i;

/** Dismiss orange/blue spend-control msgprints that block toolbar actions. */
export async function dismissAdvisoryModals(page: Page): Promise<DeskModalContent[]> {
	const dismissed: DeskModalContent[] = [];
	for (let i = 0; i < 10; i++) {
		const content = await readVisibleModal(page);
		if (!content.visible) {
			break;
		}
		if (content.kind === 'permission' && /account/i.test(content.body)) {
			break;
		}
		if (content.kind === 'error') {
			break;
		}
		if (
			content.kind === 'warning' ||
			content.kind === 'info' ||
			ADVISORY_MODAL.test(`${content.title} ${content.body}`)
		) {
			await dismissVisibleModal(page);
			dismissed.push(content);
			await page.waitForTimeout(200);
			continue;
		}
		break;
	}
	return dismissed;
}

/**
 * After Save/Submit: read modal text, assert warnings when expected, fail on
 * unexpected errors, dismiss safe dialogs so the test can continue.
 */
export async function resolvePostActionModal(
	page: Page,
	options: {
		expectWarning?: RegExp | string;
		expectError?: RegExp | string;
		allowConfirm?: boolean;
	} = {},
): Promise<DeskModalContent | null> {
	await page.waitForTimeout(300);
	let content = await readVisibleModal(page);
	if (!content.visible) {
		return null;
	}

	if (
		options.expectError &&
		content.kind === 'confirm' &&
		(options.allowConfirm === undefined || options.allowConfirm)
	) {
		await answerConfirm(page, /.*/, 'Yes');
		await page.waitForTimeout(400);
		content = await readVisibleModal(page);
		if (!content.visible) {
			return null;
		}
	}

	if (options.expectError) {
		await expect(content.body).toMatch(options.expectError);
		return content;
	}

	if (options.expectWarning) {
		if (content.kind === 'error' && options.expectWarning instanceof RegExp) {
			if (!options.expectWarning.test(content.body)) {
				throw new Error(
					`Expected warning matching ${options.expectWarning} but got [${content.kind}] "${content.body.slice(0, 240)}"`,
				);
			}
		} else if (content.kind !== 'warning' && content.kind !== 'info') {
			expect(content.kind).toMatch(/warning|info/);
		}
		await expect(content.body).toMatch(options.expectWarning);
		await dismissVisibleModal(page);
		return content;
	}

	if (content.kind === 'confirm' && options.allowConfirm) {
		await answerConfirm(page, /.*/, 'Yes');
		return content;
	}

	if (content.kind === 'warning' || content.kind === 'info') {
		await dismissVisibleModal(page);
		return content;
	}

	if (content.kind === 'permission' && /account/i.test(content.body)) {
		await dismissVisibleModal(page);
		return content;
	}

	if (content.kind === 'error' || content.kind === 'permission') {
		throw new Error(
			`Unexpected Desk modal [${content.kind}] title="${content.title}" body="${content.body.slice(0, 240)}"`,
		);
	}

	await dismissVisibleModal(page);
	return content;
}

/** Assert msgprint/confirm content and optionally dismiss. */
export async function expectMsgprint(
	page: Page,
	text: string | RegExp,
	options: { dismiss?: boolean; title?: string | RegExp } = {},
): Promise<void> {
	const { dismiss = true, title } = options;
	const content = await readVisibleModal(page);
	expect(content.visible).toBe(true);
	if (title) {
		await expect(content.title).toMatch(title);
	}
	await expect(content.body).toMatch(text);
	if (dismiss) {
		await dismissVisibleModal(page);
	}
}

/** Answer a frappe.confirm dialog. */
export async function answerConfirm(
	page: Page,
	text: string | RegExp,
	answer: 'Yes' | 'No',
): Promise<void> {
	const dialog = modal(page);
	await expect(dialog).toBeVisible({ timeout: 15000 });
	await expect(dialog.locator('.modal-body')).toContainText(text);
	const label = answer === 'Yes' ? /^(Yes|Confirm|OK)$/i : /^(No|Cancel)$/i;
	await dialog.getByRole('button', { name: label }).click();
	await dialog.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
}

/** Toast / desk alert (non-blocking). */
export async function expectToast(page: Page, text: string | RegExp): Promise<void> {
	const toast = page.locator('.toast, .desk-alert, .indicator-pill').filter({ hasText: text });
	await expect(toast.first()).toBeVisible({ timeout: 15000 });
}

/** Register handler to auto-dismiss unexpected browser dialogs (logged). */
export function autoDismissDialogs(page: Page): void {
	page.on('dialog', async (dialog) => {
		console.warn(`[e2e] auto-dismiss dialog: ${dialog.message()}`);
		await dialog.accept();
	});
}

/** Assert a thrown validation / permission error surfaced in Desk UI. */
export async function expectFormError(
	page: Page,
	text: string | RegExp,
): Promise<void> {
	const content = await readVisibleModal(page);
	if (content.visible) {
		await expect(content.body).toMatch(text);
		return;
	}
	const err = page
		.locator('.msgprint, .form-message.errors, .indicator-red')
		.filter({ hasText: text });
	await expect(err.first()).toBeVisible({ timeout: 15000 });
}
