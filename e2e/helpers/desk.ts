import { expect, type Locator, type Page } from '@playwright/test';
import {
	dismissAdvisoryModals,
	dismissIncidentalPermissionModal,
	dismissVisibleModal,
	resolvePostActionModal,
} from './dialogs';
import { formatDeskDate } from './e2e-api';

const DESK_DOC_URL = /\/(app|desk)\/[^/]+\/([^/?#]+)/;
const DESK_LIST_URL = /\/(app|desk)\/([^/?#]+)\/?$/;

export function scrubDoctype(doctype: string): string {
	return doctype.toLowerCase().replace(/ /g, '-');
}

export function formUrl(doctype: string, name?: string): string {
	const slug = scrubDoctype(doctype);
	if (!name || name === 'new') {
		return `/desk/${slug}/new`;
	}
	return `/desk/${slug}/${encodeURIComponent(name)}`;
}

/** Core Frappe Desk form interactions. */
export class DeskForm {
	constructor(readonly page: Page) {}

	async gotoForm(doctype: string, name?: string): Promise<void> {
		await this.page.goto(formUrl(doctype, name), { waitUntil: 'domcontentloaded' });
		await this.waitForFormReady();
	}

	async waitForFormReady(): Promise<void> {
		await this.page
			.locator('.form-layout, .form-page, [data-page-route]')
			.first()
			.waitFor({ state: 'visible', timeout: 45000 });
		await this.page
			.locator('.primary-action, button[data-label="Save"], .form-layout')
			.first()
			.waitFor({ state: 'visible', timeout: 45000 });
		await this.page
			.waitForFunction(
				() => {
					const win = window as unknown as { cur_frm?: { doc?: unknown } };
					return Boolean(win.cur_frm?.doc);
				},
				undefined,
				{ timeout: 30000 },
			)
			.catch(() => {});
		await this.dismissBlockingModals();
	}

	/** Dismiss known incidental modals (e.g. Account permission on Employee Advance). */
	async dismissBlockingModals(): Promise<void> {
		for (let i = 0; i < 15; i++) {
			const permission = await dismissIncidentalPermissionModal(this.page);
			if (permission) {
				await this.page.waitForTimeout(200);
				continue;
			}
			const advisory = await dismissAdvisoryModals(this.page);
			if (advisory.length) {
				await this.page.waitForTimeout(200);
				continue;
			}
			const backdrop = this.page.locator('.modal-backdrop.show');
			if (!(await backdrop.isVisible().catch(() => false))) {
				return;
			}
			await this.page.waitForTimeout(200);
		}
	}

	/** Close datepicker / awesomplete overlays that block form fields. */
	async dismissFormOverlays(): Promise<void> {
		await this.page.keyboard.press('Escape').catch(() => {});
		await this.page
			.locator('.datepicker.active, .datepicker:visible, .awesomplete:visible')
			.first()
			.waitFor({ state: 'hidden', timeout: 2000 })
			.catch(() => {});
	}

	/** Scope fields to the main form layout (avoid list/report duplicates). */
	field(fieldname: string): Locator {
		return this.page
			.locator(
				`.form-layout [data-fieldname="${fieldname}"], .form-page [data-fieldname="${fieldname}"]`,
			)
			.first();
	}

	async ensureFieldVisible(fieldname: string): Promise<Locator> {
		await this.dismissFormOverlays();
		await this.dismissBlockingModals();

		const reveal = async (): Promise<Locator> => {
			const control = this.field(fieldname);
			const section = control.locator('xpath=ancestor::div[contains(@class,"form-section")]').first();
			const collapsed = section.locator('.section-head.collapsed');
			if (await collapsed.isVisible().catch(() => false)) {
				await collapsed.click();
			}
			const tabPanel = control.locator(
				'xpath=ancestor::div[contains(@class,"tab-pane") and contains(@class,"fade")]',
			);
			const tabPanelCount = await tabPanel.count().catch(() => 0);
			if (tabPanelCount) {
				const tabId = await tabPanel.getAttribute('id');
				if (tabId) {
					const tab = this.page.locator(
						`[data-toggle="tab"][href="#${tabId}"], [role="tab"][href="#${tabId}"]`,
					);
					if (await tab.first().isVisible().catch(() => false)) {
						await tab.first().click();
					}
				}
			}
			return control;
		};

		let control = await reveal();
		if (await control.isVisible().catch(() => false)) {
			await control.scrollIntoViewIfNeeded();
			return control;
		}

		const tabs = this.page.getByRole('tab');
		const tabCount = await tabs.count();
		for (let i = 0; i < tabCount; i++) {
			await tabs.nth(i).click();
			await this.dismissFormOverlays();
			control = await reveal();
			if (await control.isVisible().catch(() => false)) {
				await control.scrollIntoViewIfNeeded();
				return control;
			}
		}

		await control.scrollIntoViewIfNeeded();
		return control;
	}

	fieldInput(fieldname: string): Locator {
		const control = this.field(fieldname);
		return control.locator('textarea, input[type="text"], input:not([type]), input[type="number"]').first();
	}

	async fillData(fieldname: string, value: string): Promise<void> {
		await this.dismissBlockingModals();
		const control = await this.ensureFieldVisible(fieldname);
		const input = control
			.locator('textarea, input[type="text"], input:not([type]), input[type="number"]')
			.first();
		await input.scrollIntoViewIfNeeded();
		await input.click();
		await input.fill(value);
		await input.blur();
	}

	async fillInt(fieldname: string, value: number | string): Promise<void> {
		await dismissIncidentalPermissionModal(this.page);
		const control = await this.ensureFieldVisible(fieldname);
		const input = control.locator('input').first();
		await input.scrollIntoViewIfNeeded();
		await input.click();
		await input.fill(String(value));
		await input.blur();
	}

	async fillFloat(fieldname: string, value: number | string): Promise<void> {
		await this.fillInt(fieldname, value);
	}

	async fillDate(fieldname: string, isoDate: string): Promise<void> {
		await this.fillData(fieldname, formatDeskDate(isoDate));
		await this.page.keyboard.press('Escape');
		await this.page.locator('.datepicker:visible').waitFor({ state: 'hidden', timeout: 5000 }).catch(() => {});
	}

	async commitGridEdits(): Promise<void> {
		await this.page.locator('.page-head').click({ position: { x: 10, y: 10 } }).catch(() => {});
		await this.page.keyboard.press('Escape');
	}

	async fillSelect(fieldname: string, value: string): Promise<void> {
		const control = await this.ensureFieldVisible(fieldname);
		const select = control.locator('select');
		if (await select.count()) {
			await select.selectOption(value);
			return;
		}
		await this.fillData(fieldname, value);
	}

	async fillLink(fieldname: string, value: string): Promise<void> {
		await dismissIncidentalPermissionModal(this.page);
		const control = await this.ensureFieldVisible(fieldname);
		let input = control.getByRole('combobox').first();
		if (!(await input.isVisible().catch(() => false))) {
			input = control.locator('input').first();
		}
		if (await input.isDisabled().catch(() => false)) {
			const current = (await input.inputValue()) || '';
			if (current.includes(value)) {
				return;
			}
			throw new Error(`Link field ${fieldname} is read-only; expected to contain "${value}" but has "${current}"`);
		}
		await input.scrollIntoViewIfNeeded();
		await input.click();
		await input.fill('');
		await input.fill(value);
		await this.page.waitForTimeout(500);
		const suggestions = this.page.locator(
			'.awesomplete ul li:visible, .link-options .dropdown-item:visible, .dropdown-menu.show a:visible, [role="option"]:visible',
		);
		const exact = suggestions.filter({ hasText: value }).first();
		if (await exact.isVisible({ timeout: 8000 }).catch(() => false)) {
			await exact.click();
		} else {
			const advanced = this.page
				.locator('.awesomplete ul li:visible')
				.filter({ hasText: /Advanced Search/i })
				.first();
			if (await advanced.isVisible({ timeout: 3000 }).catch(() => false)) {
				await advanced.click();
				await this.pickFromLinkDialog(value);
			} else {
				await input.press('ArrowDown').catch(() => {});
				await input.press('Enter').catch(() => {});
			}
		}
		let linked = await this.waitForLinkField(fieldname, value);
		if (!linked) {
			const advanced = this.page
				.locator('.awesomplete ul li:visible')
				.filter({ hasText: /Advanced Search/i })
				.first();
			if (await advanced.isVisible({ timeout: 2000 }).catch(() => false)) {
				await advanced.click();
				await this.pickFromLinkDialog(value);
			} else {
				const control = await this.ensureFieldVisible(fieldname);
				const linkBtn = control.locator('.link-btn, .btn-open').first();
				if (await linkBtn.isVisible().catch(() => false)) {
					await linkBtn.click();
				}
				await this.pickFromLinkDialog(value);
			}
			linked = await this.waitForLinkField(fieldname, value);
		}
		if (!linked) {
			throw new Error(`Link field ${fieldname} did not resolve to "${value}"`);
		}
		if (fieldname === 'employee') {
			await this.page
				.waitForFunction(
					() => Boolean((window as unknown as { cur_frm?: { doc?: { company?: string } } }).cur_frm?.doc?.company),
					undefined,
					{ timeout: 15000 },
				)
				.catch(() => {});
		}
	}

	private async waitForLinkField(fieldname: string, value: string): Promise<boolean> {
		return Boolean(
			await this.page
				.waitForFunction(
					({ field, val }) => {
						const current =
							(window as unknown as { cur_frm?: { doc?: Record<string, string> } }).cur_frm?.doc?.[
								field
							] || '';
						if (/^[A-Z][A-Z0-9]*-[A-Z][A-Z0-9]*-\d+/.test(val)) {
							return current === val || String(current).includes(val);
						}
						return Boolean(current);
					},
					{ field: fieldname, val: value },
					{ timeout: 8000 },
				)
				.catch(() => null),
		);
	}

	private linkDialogSearchTerm(value: string, displayName?: string): string {
		// Frappe link dialog uses "Beginning with" on the name field when searchfield=name.
		if (/^HR-EMP-/.test(value)) {
			return value;
		}
		if (displayName?.startsWith('E2E')) {
			return 'E2E';
		}
		return displayName || value;
	}

	protected async pickFromLinkDialog(value: string, control?: Locator, displayName?: string): Promise<void> {
		if (control) {
			const linkBtn = control.locator('.link-btn, .btn-open').first();
			if (await linkBtn.isVisible().catch(() => false)) {
				await linkBtn.click();
			}
		}
		const dialog = this.page.locator('.modal.show, .modal.in, [role="dialog"]').last();
		await dialog.waitFor({ state: 'visible', timeout: 10000 });
		const body = dialog.locator('.modal-body');
		const search = dialog.locator('input[type="search"], input.input-with-feedback, .form-control').first();
		const searchTerm = this.linkDialogSearchTerm(value, displayName);
		if (await search.isVisible().catch(() => false)) {
			await search.fill(searchTerm);
			const searchBtn = dialog.getByRole('button', { name: /^Search$/i });
			if (await searchBtn.isVisible().catch(() => false)) {
				await searchBtn.click();
				await body.getByText(value, { exact: true }).first().waitFor({ state: 'visible', timeout: 8000 }).catch(() => {});
				await this.page.waitForTimeout(400);
			}
		}
		const wantsId = /^[A-Z][A-Z0-9]*-[A-Z][A-Z0-9]*-\d+/.test(value);
		if (wantsId) {
			const idCell = body.getByText(value, { exact: true });
			for (let i = 0; i < (await idCell.count()); i++) {
				const candidate = idCell.nth(i);
				if (await candidate.isVisible().catch(() => false)) {
					await candidate.scrollIntoViewIfNeeded();
					await candidate.click({ force: true });
					await dialog.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
					return;
				}
			}
		}
		const clicked = await dialog.evaluate(
			({ id, name }) => {
				const modal = document.querySelector('.modal.show .modal-body, .modal.in .modal-body');
				if (!modal) {
					return false;
				}
				const scrollers = [modal, ...Array.from(modal.querySelectorAll('*'))].filter(
					(el) => el.scrollHeight > el.clientHeight + 5,
				) as HTMLElement[];
				const tryClick = (): boolean => {
					const nodes = Array.from(
						modal.querySelectorAll('a, tr, .list-row, .list-item, [class*="list-row"], p, span, div'),
					);
					const wantsDocId = /^[A-Z][A-Z0-9]*-[A-Z][A-Z0-9]*-\d+/.test(id);
					for (const node of nodes) {
						const el = node as HTMLElement;
						if (['INPUT', 'BUTTON', 'TEXTAREA'].includes(el.tagName)) {
							continue;
						}
						if (!el.offsetParent || getComputedStyle(el).visibility === 'hidden') {
							continue;
						}
						const text = (el.textContent || '').replace(/\s+/g, ' ').trim();
						if (!text || text.length > 200) {
							continue;
						}
						if (wantsDocId) {
							if (!text.includes(id)) {
								continue;
							}
						} else if (name && !text.includes(name)) {
							continue;
						} else if (!text.includes(id)) {
							continue;
						}
						const row = (el.closest('a, tr, .list-row, .list-item, [class*="list-row"]') ||
							el) as HTMLElement;
						row.click();
						return true;
					}
					return false;
				};
				if (tryClick()) {
					return true;
				}
				for (const scroller of scrollers) {
					for (let offset = 0; offset <= scroller.scrollHeight; offset += 48) {
						scroller.scrollTop = offset;
						if (tryClick()) {
							return true;
						}
					}
				}
				return false;
			},
			{ id: value, name: displayName || '' },
		);
		if (clicked) {
			await dialog.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
			return;
		}
		const matches = body.getByText(value, { exact: true });
		for (let i = 0; i < (await matches.count()); i++) {
			const candidate = matches.nth(i);
			if (await candidate.isVisible().catch(() => false)) {
				await candidate.click();
				await dialog.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
				return;
			}
		}
		if (displayName) {
			const nameMatches = body.getByText(displayName, { exact: true });
			for (let i = 0; i < (await nameMatches.count()); i++) {
				const candidate = nameMatches.nth(i);
				if (await candidate.isVisible().catch(() => false)) {
					await candidate.click();
					await dialog.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
					return;
				}
			}
		}
		throw new Error(`Link dialog: no visible result for "${displayName || value}"`);
	}

	async setCheck(fieldname: string, checked: boolean): Promise<void> {
		const control = await this.ensureFieldVisible(fieldname);
		const box = control.locator('input[type="checkbox"]');
		if (!(await box.isVisible().catch(() => false))) {
			throw new Error(`Checkbox ${fieldname} is not visible in Desk UI`);
		}
		if (checked) {
			await box.check();
		} else {
			await box.uncheck();
		}
	}

	async readLinkValue(fieldname: string): Promise<string> {
		return (await this.field(fieldname).locator('input').first().inputValue()) || '';
	}

	async readDataValue(fieldname: string): Promise<string> {
		const control = this.field(fieldname);
		const input = control.locator('textarea, input').first();
		return (await input.inputValue()) || '';
	}

	grid(tableFieldname: string): Locator {
		return this.page
			.locator(
				`[data-fieldname="${tableFieldname}"] .grid-body, [data-fieldname="${tableFieldname}"] .form-grid`,
			)
			.first();
	}

	async gridRowCount(tableFieldname: string): Promise<number> {
		return this.page
			.locator(`[data-fieldname="${tableFieldname}"] .grid-row, [data-fieldname="${tableFieldname}"] .form-grid-row`)
			.count();
	}

	async getOrCreateEditableRow(tableFieldname: string, emptyCheckField = 'task_title'): Promise<number> {
		await this.dismissBlockingModals();
		const count = await this.gridRowCount(tableFieldname);
		if (count === 0) {
			return this.addGridRow(tableFieldname);
		}
		for (let i = 0; i < count; i++) {
			await this.openGridRowForEdit(tableFieldname, i);
			const cell = this.gridRow(tableFieldname, i).locator(`[data-fieldname="${emptyCheckField}"] input`);
			if (!(await cell.isVisible().catch(() => false))) {
				continue;
			}
			const value = ((await cell.inputValue().catch(() => '')) || '').trim();
			if (!value) {
				return i;
			}
		}
		return this.addGridRow(tableFieldname);
	}

	async removeGridRow(tableFieldname: string, rowIndex: number): Promise<void> {
		const grid = this.page.locator(`[data-fieldname="${tableFieldname}"]`);
		const row = this.gridRow(tableFieldname, rowIndex);
		const checkbox = row.locator('.grid-row-check, input[type="checkbox"]').first();
		await checkbox.check();
		const removeBtn = grid.locator(
			'.grid-remove-rows, .grid-remove-all-rows, button:has-text("Delete Rows"), button:has-text("Delete")',
		);
		if (await removeBtn.first().isVisible().catch(() => false)) {
			await removeBtn.first().click();
			return;
		}
		await row.locator('.grid-delete-row, .btn-open-row').filter({ hasText: /delete|remove/i }).first().click();
	}

	/** Remove blank rows above the row we just filled (Frappe keeps a placeholder row 1). */
	async pruneEmptyGridRowsAbove(tableFieldname: string, keepRowIndex: number): Promise<void> {
		for (let i = keepRowIndex - 1; i >= 0; i--) {
			await this.removeGridRow(tableFieldname, i);
		}
	}

	/** Reset a child table the same way Desk does before adding rows in tests. */
	async clearChildTable(tableFieldname: string): Promise<void> {
		await this.page.evaluate((table) => {
			const frm = (window as unknown as { cur_frm?: { clear_table: (t: string) => void } }).cur_frm;
			frm?.clear_table(table);
		}, tableFieldname);
	}

	async addGridRow(tableFieldname: string): Promise<number> {
		await this.dismissBlockingModals();
		const grid = this.page.locator(`[data-fieldname="${tableFieldname}"]`);
		const before = await this.gridRowCount(tableFieldname);
		const addBtn = grid
			.locator('button.grid-add-row, .grid-add-row, .btn:has-text("Add Row"), .btn:has-text("Add row")')
			.first();
		await addBtn.scrollIntoViewIfNeeded();
		await addBtn.click();
		await expect
			.poll(() => this.gridRowCount(tableFieldname), { timeout: 10000 })
			.toBeGreaterThan(before);
		const after = await this.gridRowCount(tableFieldname);
		const rowIndex = after - 1;
		await this.openGridRowForEdit(tableFieldname, rowIndex);
		return rowIndex;
	}

	gridRow(tableFieldname: string, rowIndex = 0): Locator {
		return this.page
			.locator(
				`[data-fieldname="${tableFieldname}"] .grid-row, [data-fieldname="${tableFieldname}"] .form-grid-row`,
			)
			.nth(rowIndex);
	}

	async openGridRowForEdit(tableFieldname: string, rowIndex: number): Promise<void> {
		const row = this.gridRow(tableFieldname, rowIndex);
		const editable = row.locator('input:visible, textarea:visible, [role="combobox"]:visible').first();
		if (await editable.isVisible().catch(() => false)) {
			return;
		}
		await row.scrollIntoViewIfNeeded();
		const editBtn = row.locator('.btn-open-row, .edit-grid-row, .row-index').last();
		if (await editBtn.isVisible().catch(() => false)) {
			await editBtn.click();
		} else {
			await row.dblclick();
		}
		await row
			.locator('input:visible, textarea:visible, [role="combobox"]:visible')
			.first()
			.waitFor({ state: 'visible', timeout: 10000 });
	}

	async fillGridField(
		tableFieldname: string,
		rowIndex: number,
		fieldname: string,
		value: string,
	): Promise<void> {
		await dismissIncidentalPermissionModal(this.page);
		await this.openGridRowForEdit(tableFieldname, rowIndex);
		const row = this.gridRow(tableFieldname, rowIndex);
		const cell = row.locator(`[data-fieldname="${fieldname}"]`);
		let input = cell.getByRole('combobox').first();
		if (!(await input.isVisible().catch(() => false))) {
			input = cell.locator('input:visible, textarea:visible').first();
		}
		await input.scrollIntoViewIfNeeded();
		await input.click();
		await input.fill(value);
		const isLink =
			fieldname === 'project' || (await cell.locator('[data-fieldtype="Link"]').count()) > 0;
		if (isLink) {
			const option = this.page
				.locator('.awesomplete ul li, .link-options .dropdown-item, [role="option"]')
				.filter({ hasText: value })
				.first();
			if (await option.isVisible({ timeout: 5000 }).catch(() => false)) {
				await option.click();
			} else {
				await input.press('ArrowDown').catch(() => {});
				await input.press('Enter').catch(() => {});
			}
		}
		await input.press('Tab').catch(() => {});
		await this.dismissBlockingModals();
	}

	async fillGridLinkField(
		tableFieldname: string,
		rowIndex: number,
		fieldname: string,
		value: string,
	): Promise<void> {
		await this.dismissBlockingModals();
		await this.openGridRowForEdit(tableFieldname, rowIndex);
		const row = this.gridRow(tableFieldname, rowIndex);
		const cell = row.locator(`[data-fieldname="${fieldname}"]`);
		let input = cell.getByRole('combobox').first();
		if (!(await input.isVisible().catch(() => false))) {
			input = cell.locator('input:visible').first();
		}
		await input.click();
		await input.fill('');
		await input.fill(value);
		await this.page.waitForTimeout(400);
		const exact = this.page.locator('.awesomplete ul li:visible').filter({ hasText: value }).first();
		if (await exact.isVisible({ timeout: 5000 }).catch(() => false)) {
			await exact.click();
		} else {
			const advanced = this.page
				.locator('.awesomplete ul li:visible')
				.filter({ hasText: /Advanced Search/i })
				.first();
			if (await advanced.isVisible({ timeout: 2000 }).catch(() => false)) {
				await advanced.click({ force: true });
				await this.pickFromLinkDialog(value);
			} else {
				await input.press('ArrowDown').catch(() => {});
				await input.press('Enter').catch(() => {});
			}
		}
		await this.commitGridEdits();
		await this.dismissBlockingModals();
	}

	async clickTab(label: string): Promise<void> {
		await this.dismissBlockingModals();
		const tab = this.page.getByRole('tab', { name: label });
		if (!(await tab.isVisible().catch(() => false))) {
			return;
		}
		const isActive = await tab.evaluate((el) => el.classList.contains('active')).catch(() => false);
		if (isActive) {
			return;
		}
		await tab.click();
		await this.dismissBlockingModals();
	}

	async trySaveExpectError(errorPattern: RegExp | string): Promise<void> {
		await this.commitGridEdits();
		await this.clickPrimary('Save', { expectError: errorPattern });
	}

	async clickPrimary(
		label: string,
		options?: { expectWarning?: RegExp | string; allowConfirm?: boolean; expectError?: RegExp | string },
	): Promise<void> {
		const toolbar = this.page.locator('.page-head, .page-actions, .standard-actions');
		let btn = toolbar.getByRole('button', { name: label, exact: true }).first();
		if (!(await btn.isVisible().catch(() => false))) {
			btn = this.page
				.locator(`.primary-action, button[data-label="${label}"]`)
				.filter({ hasText: label })
				.and(this.page.locator(':visible'))
				.first();
		}
		await btn.waitFor({ state: 'visible', timeout: 15000 });
		await btn.click();
		await resolvePostActionModal(this.page, options);
	}

	async save(options?: { expectWarning?: RegExp | string; expectError?: RegExp | string }): Promise<void> {
		await this.commitGridEdits();
		await this.clickPrimary('Save', options);
		if (!options?.expectError) {
			await this.page.waitForURL(DESK_DOC_URL, { timeout: 30000 }).catch(() => {});
		}
		await this.page.locator('.indicator-pill, .form-docstatus').filter({ hasText: /Saved|Not Saved/i }).first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => {});
	}

	async submit(options?: {
		expectWarning?: RegExp | string;
		allowConfirm?: boolean;
		expectError?: RegExp | string;
	}): Promise<void> {
		await this.commitGridEdits();
		await this.dismissBlockingModals();
		const toolbar = this.page.locator('.page-head, .page-actions, .standard-actions');
		const submitBtn = toolbar
			.getByRole('button', { name: 'Submit', exact: true })
			.and(this.page.locator(':visible'))
			.first();
		if (await submitBtn.isVisible().catch(() => false)) {
			await submitBtn.click();
			await resolvePostActionModal(this.page, { allowConfirm: true, ...options });
			return;
		}
		await this.openMenuAction('Submit');
		await resolvePostActionModal(this.page, { allowConfirm: true, ...options });
	}

	async cancelDoc(): Promise<void> {
		await this.openMenuAction('Cancel');
		await resolvePostActionModal(this.page, { allowConfirm: true });
	}

	async openMenuAction(action: string): Promise<void> {
		await this.dismissBlockingModals();
		const menuBtn = this.page
			.locator('.page-actions .btn, .actions-btn-group .btn, .menu-btn-group .btn')
			.filter({ hasText: /Actions|Menu/i })
			.and(this.page.locator(':visible'))
			.first();
		if (await menuBtn.isVisible().catch(() => false)) {
			await menuBtn.click();
		}
		const item = this.page
			.locator('.dropdown-menu.show .dropdown-item')
			.filter({ hasText: action })
			.and(this.page.locator(':visible'))
			.first();
		await item.waitFor({ state: 'visible', timeout: 15000 });
		await item.click();
	}

	async clickWorkflowAction(
		action: string,
		options?: { expectError?: RegExp | string; allowConfirm?: boolean },
	): Promise<void> {
		await this.dismissBlockingModals();
		const primary = this.page
			.locator('.page-head .primary-action, .page-actions .primary-action')
			.filter({ hasText: new RegExp(`^\\s*${action}\\s*$`) })
			.and(this.page.locator(':visible'))
			.first();
		if (!options?.expectError) {
			await primary.waitFor({ state: 'visible', timeout: 30000 }).catch(() => {});
		}
		if ((await primary.isVisible().catch(() => false)) && !options?.expectError) {
			await primary.click();
			await resolvePostActionModal(this.page, { allowConfirm: true, ...options });
			return;
		}
		const actionsBtn = this.page
			.locator('.actions-btn-group .btn, button:has-text("Actions")')
			.and(this.page.locator(':visible'))
			.first();
		if (await actionsBtn.isVisible().catch(() => false)) {
			await actionsBtn.click();
		}
		const item = this.page
			.locator(`.dropdown-menu.show .dropdown-item[data-label="${action}"], .dropdown-menu.show .dropdown-item`)
			.filter({ hasText: new RegExp(`^\\s*${action}\\s*$`) })
			.first();
		await item.waitFor({ state: 'visible', timeout: 15000 });
		await item.click();
		await resolvePostActionModal(this.page, { allowConfirm: options?.expectError ? false : true, ...options });
	}

	async workflowActionVisible(action: string): Promise<boolean> {
		const actionsBtn = this.page.locator('.actions-btn-group .btn, button:has-text("Actions")');
		if (await actionsBtn.first().isVisible().catch(() => false)) {
			await actionsBtn.first().click();
		}
		const item = this.page.locator('.dropdown-item, button').filter({ hasText: action });
		const visible = await item.first().isVisible().catch(() => false);
		await this.page.keyboard.press('Escape').catch(() => {});
		return visible;
	}

	async clickCustomButton(label: string): Promise<void> {
		const btn = this.page.locator(`.custom-btn, button`).filter({ hasText: label }).first();
		await btn.click();
		await resolvePostActionModal(this.page, { allowConfirm: true });
	}

	getDocNameFromUrl(): string | null {
		const match = this.page.url().match(DESK_DOC_URL);
		if (!match || match[2] === 'new') {
			return null;
		}
		return decodeURIComponent(match[2]);
	}

	async expectDocstatus(expected: number): Promise<void> {
		const indicator = this.page.locator('.indicator-pill, .docstatus');
		if (expected === 1) {
			await expect(indicator.filter({ hasText: /Submitted|Approved/i }).first()).toBeVisible({
				timeout: 15000,
			});
		}
	}

	async gotoList(doctype: string): Promise<void> {
		const slug = scrubDoctype(doctype);
		await this.page.goto(`/desk/${slug}`, { waitUntil: 'domcontentloaded' });
		await this.page.locator('.list-row, .frappe-list').first().waitFor({ state: 'visible', timeout: 30000 });
	}

	async gotoReport(reportTitle: string): Promise<void> {
		const encoded = encodeURIComponent(reportTitle);
		await this.page.goto(`/desk/query-report/${encoded}`, { waitUntil: 'domcontentloaded' });
		await this.page.locator('.report-wrapper, .query-report').first().waitFor({
			state: 'visible',
			timeout: 45000,
		});
	}

	async gotoPage(pageName: string): Promise<void> {
		const slug = pageName.toLowerCase().replace(/ /g, '-');
		await this.page.goto(`/desk/${slug}`, { waitUntil: 'domcontentloaded' });
	}

	async closeOpenModals(): Promise<void> {
		for (let i = 0; i < 3; i++) {
			const content = await dismissIncidentalPermissionModal(this.page);
			if (!content) {
				break;
			}
		}
		await dismissVisibleModal(this.page).catch(() => {});
	}
}
