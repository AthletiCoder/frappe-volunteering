import { expect, type Page } from '@playwright/test';

export function requireLocalRegression(baseURL?: string) {
	if (!baseURL || !['127.0.0.1', 'localhost', 'sevamrita.local'].includes(new URL(baseURL).hostname))
		throw new Error('Accounting/administration regression writes are restricted to localhost.');
}

export async function portalCall(page: Page, method: string, args: Record<string, unknown> = {}) {
	return page.evaluate(async ({ method, args }) => {
		const response = await fetch(`/api/method/${method}`, {
			method: 'POST', credentials: 'same-origin',
			headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': (window as any).csrf_token || '' },
			body: JSON.stringify(args),
		});
		const body = await response.json();
		if (!response.ok || body.exc || body.exception) throw new Error(`${response.status}: ${JSON.stringify(body)}`);
		return body.message;
	}, { method, args });
}

export async function chooseSearch(page: Page, label: string, search: string) {
	const select = page.getByRole('combobox', { name: label, exact: true });
	await select.fill(search);
	// Exact typed matches can auto-select and reopen all suggestions. Never
	// assume the first option is the requested item/account in a real database.
	const escaped = [...search].map(char => '.*+?^${}()|[]'.includes(char) || char.charCodeAt(0) === 92 ? String.fromCharCode(92) + char : char).join('');
	await page.getByRole('listbox', { name: label, exact: true }).getByRole('option', { name: new RegExp(escaped, 'i') }).first().click();
	await expect(select).toHaveValue(new RegExp(escaped, 'i'));
}

// Valid one-page fixture with visible QA markings, not a real supplier invoice.
export function qaReceipt(text: string) {
	const newline = String.fromCharCode(10);
	const safeText = [...text].filter(char => !['(', ')', String.fromCharCode(92)].includes(char)).join('');
	const stream = `BT /F1 16 Tf 50 780 Td (QA ONLY - NO REAL TRANSACTION) Tj 0 -30 Td (${safeText}) Tj ET`;
	const objects = [
		'<< /Type /Catalog /Pages 2 0 R >>',
		'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
		'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
		'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
		[`<< /Length ${Buffer.byteLength(stream)} >>`, 'stream', stream, 'endstream'].join(newline),
	];
	let pdf = '%PDF-1.4' + newline;
	const offsets = [0];
	objects.forEach((object, index) => { offsets.push(Buffer.byteLength(pdf)); pdf += [`${index + 1} 0 obj`, object, 'endobj', ''].join(newline); });
	const xref = Buffer.byteLength(pdf);
	pdf += ['xref', '0 6', '0000000000 65535 f ', ...offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n `), 'trailer', '<< /Size 6 /Root 1 0 R >>', 'startxref', String(xref), '%%EOF', ''].join(newline);
	return { name: 'qa-purchase-bill.pdf', mimeType: 'application/pdf', buffer: Buffer.from(pdf) };
}

export async function expectNoDesk(page: Page) {
	expect(new URL(page.url()).pathname).toMatch(/^\/volunteering\//);
	await expect(page.locator('.desk-page, .form-layout')).toHaveCount(0);
}
