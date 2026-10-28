import { expect, test, type Page } from '@playwright/test';
import { loginViaAPI } from '../../helpers/auth';
import { PERSONAS } from '../../helpers/personas';
import { portalCall, qaReceipt, requireLocalRegression } from '../../helpers/portal-regression';

const CLAIM = 'volunteering.volunteering.expense_claim_portal.';

async function sign(page: Page) {
	await page.getByRole('button', { name: 'Sign freshly', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'Volunteer sign on screen' });
	const box = await dialog.locator('canvas').boundingBox();
	expect(box).toBeTruthy();
	await page.mouse.move(box!.x + 35, box!.y + 80);
	await page.mouse.down();
	for (const [x, y] of [[65, 30], [80, 100], [110, 45], [140, 100], [180, 60]])
		await page.mouse.move(box!.x + x, box!.y + y, { steps: 8 });
	await page.mouse.up();
	await dialog.getByRole('button', { name: 'Use this signature', exact: true }).click();
	await expect(dialog).toHaveCount(0);
	await expect(page.getByAltText('Volunteer signature preview')).toBeVisible();
}

test('Signed combined invoice → private PDF → receipt correction → employee resubmission → verified', async ({ page, browser, baseURL }, testInfo) => {
	requireLocalRegression(baseURL);
	test.setTimeout(180_000);
	await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
	await page.goto('/volunteering/invoice-expense-claim');
	await expect(page.getByRole('heading', { name: 'Prepare invoice and submit expense', exact: true })).toBeVisible();
	const defaults = await portalCall(page, CLAIM + 'get_expense_claim_form');
	expect(defaults.projects.length).toBeGreaterThan(0);
	await page.getByRole('combobox', { name: 'Project *', exact: true }).selectOption(defaults.projects[0].value);
	await page.getByRole('button', { name: /^No, prepare one now/ }).click();
	await page.getByRole('combobox', { name: 'Project expense category *', exact: true }).click();
	await page.getByRole('listbox', { name: 'Project expense category *', exact: true }).getByRole('option').first().click();
	await page.getByLabel('Description and business purpose *', { exact: true }).fill('QA ONLY: utensils for a fictional training kitchen');
	const invoice = page.getByRole('region', { name: 'Invoice generation' });
	await invoice.getByLabel('Legal name *', { exact: true }).fill('QA Training Utensils Supplier');
	await invoice.getByLabel('Address *', { exact: true }).fill('10 Training Lane, Pune, Maharashtra 411045');
	await invoice.getByLabel('State *', { exact: true }).fill('Maharashtra');
	await invoice.getByLabel('Description *', { exact: true }).fill('QA ONLY demonstration kitchen spoon');
	await invoice.getByLabel('Rate (INR) *', { exact: true }).fill('75');
	await expect(page.getByLabel('Generated invoice total', { exact: true })).toHaveValue('₹75.00');
	await expect(invoice.getByRole('button', { name: /^Generate (PDF|Word)$/ })).toHaveCount(0);
	await sign(page);
	await invoice.getByLabel('Rate (INR) *', { exact: true }).fill('80');
	await expect(page.getByAltText('Volunteer signature preview')).toHaveCount(0);
	await expect(invoice.getByRole('alert')).toContainText(/changed.*sign.*again/i);
	await sign(page);
	const submitted = page.waitForResponse(response => response.url().includes('expense_claim_portal.submit_generated_invoice_expense_claim'));
	await page.getByRole('button', { name: 'Sign and submit for receipt review', exact: true }).click();
	const response = await submitted;
	expect(response.status(), await response.text()).toBe(200);
	const created = (await response.json()).message;
	expect(created.generated_invoice_number).toMatch(/^INV-\d{4}-\d+$/);
	expect(created.total).toBe(80);
	await expect(page.getByRole('heading', { name: 'Sent for receipt review', exact: true })).toBeVisible();
	await testInfo.attach('created-combined-claim', { body: JSON.stringify(created, null, 2), contentType: 'application/json' });
	await page.getByRole('link', { name: 'Track this claim' }).click();
	const receipt = page.getByRole('link', { name: 'View attached receipt', exact: true });
	const originalURL = await receipt.getAttribute('href');
	expect(originalURL).toMatch(/^\/private\/files\/.+\.pdf$/);
	const pdf = await page.request.get(originalURL!);
	expect(pdf.status()).toBe(200);
	expect((await pdf.body()).subarray(0, 5).toString()).toBe('%PDF-');

	const reviewerContext = await browser.newContext();
	try {
		const reviewer = await reviewerContext.newPage();
		await loginViaAPI(reviewer.request, PERSONAS.receipt_reviewer.email, PERSONAS.receipt_reviewer.password);
		const reviewURL = '/volunteering/expense-claim-workflow?claim=' + encodeURIComponent(created.name);
		await reviewer.goto(reviewURL);
		await expect(reviewer.getByRole('link', { name: 'Open private receipt', exact: true })).toHaveAttribute('href', originalURL!);
		await reviewer.getByLabel('Review notes', { exact: true }).fill('QA: please clarify the utensil description and attach the corrected bill.');
		await reviewer.getByRole('button', { name: 'Request correction', exact: true }).click();
		await expect(reviewer.getByText('The claim was returned to the employee for correction.', { exact: true })).toBeVisible();
		await page.reload();
		await page.getByRole('link', { name: 'Correct and resubmit', exact: true }).click();
		await expect(page.getByText('Why correction was requested', { exact: true })).toBeVisible();
		await page.getByLabel('Description and business purpose *', { exact: true }).fill('QA ONLY: corrected description — one demonstration kitchen spoon');
		await page.getByLabel('Receipt evidence *', { exact: true }).setInputFiles(qaReceipt('Corrected QA bill: one spoon INR 80'));
		await page.getByLabel('Correction note', { exact: true }).fill('Clarified the item and replaced the QA bill; amount unchanged.');
		const resubmitted = page.waitForResponse(result => result.url().includes('expense_claim_portal.resubmit_expense_claim'));
		await page.getByRole('button', { name: 'Resubmit for receipt review', exact: true }).click();
		const correctedResponse = await resubmitted;
		expect(correctedResponse.status(), await correctedResponse.text()).toBe(200);
		await expect(page.getByRole('heading', { name: 'Corrections sent for receipt review', exact: true })).toBeVisible();
		// Recording a decision returns the reviewer to the queue. Reopen the
		// resubmitted claim rather than reloading that queue URL.
		await reviewer.goto(reviewURL);
		const correctedURL = await reviewer.getByRole('link', { name: 'Open private receipt', exact: true }).getAttribute('href');
		expect(correctedURL).not.toBe(originalURL);
		expect((await reviewer.request.get(correctedURL!)).status()).toBe(200);
		await reviewer.getByLabel('Review notes', { exact: true }).fill('Corrected QA receipt verified.');
		await reviewer.getByRole('button', { name: 'Verify receipts', exact: true }).click();
		await expect(reviewer.getByText('Receipts verified; the claim is now with its manager.', { exact: true })).toBeVisible();
		await page.goto('/volunteering/expense-claims?claim=' + encodeURIComponent(created.name));
		await expect(page.getByRole('heading', { name: created.name, exact: true })).toBeVisible();
		await expect(page.getByRole('heading', { name: 'Status history', exact: true })).toBeVisible();
		const detail = await portalCall(page, CLAIM + 'get_my_expense_claim', { name: created.name });
		expect(detail.workflow_state).toBe('Pending Approval');
		expect(detail.receipt_review_status).toBe('Verified');
	} finally {
		await reviewerContext.close();
	}
});
