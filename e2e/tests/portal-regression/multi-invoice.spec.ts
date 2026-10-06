import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

const API = "volunteering.volunteering.expense_claim_portal.";

async function call(page: Page, method: string, args = {}) {
  return page.evaluate(async ({ method, args }) => {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": (window as any).csrf_token || "" },
      credentials: "same-origin",
      body: JSON.stringify(args),
    });
    if (!response.ok) throw new Error(`API ${method} failed: ${response.status}`);
    return (await response.json()).message;
  }, { method, args });
}

test.beforeEach(async ({ page, baseURL }) => {
  if (!baseURL || !["127.0.0.1", "localhost", "sevamrita.local"].includes(new URL(baseURL).hostname)) {
    throw new Error("Multi-invoice regression must run against the local demo site only.");
  }
  await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
});

test("the employee can reach a separate multi-invoice form with two dated bills", async ({ page }) => {
  await page.goto("/volunteering/expense-claim");
  await page.getByRole("link", { name: "Submit multiple invoices" }).click();
  await expect(page).toHaveURL(/\/volunteering\/expense-claim\/multiple/);
  await expect(page.getByRole("heading", { name: "Submit multiple invoices" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Invoice [12]$/ })).toHaveCount(2);
  await expect(page.getByLabel("Date shown on invoice *")).toHaveCount(2);
  await expect(page.getByLabel(/Invoice or bill/)).toHaveCount(2);
  await page.getByRole("button", { name: "+ Add invoice" }).click();
  await expect(page.getByRole("heading", { name: "Invoice 3" })).toBeVisible();
  await page.locator("section.form-card").filter({ has: page.getByRole("heading", { name: "Invoice 3" }) }).getByRole("button", { name: "Remove invoice" }).click();
  await expect(page.getByRole("heading", { name: "Invoice 3" })).toHaveCount(0);
});

test("two invoice dates create two separately dated claims with one submission ID", async ({ page }) => {
  test.skip(process.env.E2E_MULTI_INVOICE_WRITES !== "1", "Opt-in local accounting write.");
  await page.goto("/volunteering/expense-claim/multiple");
  await expect(page.getByRole("heading", { name: "Submit multiple invoices" })).toBeVisible();
  const defaults = await call(page, API + "get_expense_claim_form");
  expect(defaults.projects.length).toBeGreaterThan(0);
  const project = defaults.projects[0].value;
  const accounts = await call(page, API + "get_project_accounts", { project });
  expect(accounts.length).toBeGreaterThan(0);
  await page.getByLabel("Project *").selectOption(project);
  const today = defaults.expense_date;
  const prior = new Date(`${today}T12:00:00Z`);
  prior.setUTCDate(prior.getUTCDate() - 1);
  const yesterday = prior.toISOString().slice(0, 10);
  const file = {
    name: "local-test-bill.png",
    mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlVAAAAAASUVORK5CYII=", "base64"),
  };
  for (const [index, date] of [yesterday, today].entries()) {
    const invoice = page.locator("section.form-card").filter({ has: page.getByRole("heading", { name: `Invoice ${index + 1}`, exact: true }) });
    await invoice.getByLabel("Date shown on invoice *").fill(date);
    await invoice.getByLabel("Invoice number").fill(`LOCAL-MULTI-${Date.now()}-${index + 1}`);
    await invoice.getByLabel("Supplier / payee").fill("Local regression supplier");
    await invoice.getByLabel(/Invoice or bill/).setInputFiles(file);
    const category = invoice.getByRole("combobox", { name: "Project expense category *" });
    await category.click();
    await invoice.getByRole("listbox", { name: "Project expense category *" }).getByRole("option").first().click();
    await invoice.getByLabel(/Amount \(/).fill(String(index + 1));
    await invoice.getByLabel("Description and business purpose *").fill("Fictional local regression expense");
  }
  await page.getByRole("button", { name: "Submit all invoices for review" }).click();
  await expect(page.getByRole("heading", { name: "Sent for receipt review" })).toBeVisible();
  const claimLinks = page.locator("main a[href*='expense-claims?claim=']");
  await expect(claimLinks).toHaveCount(2);
  const names = await claimLinks.allTextContents();
  const history = await call(page, API + "get_my_expense_claims");
  const submitted = history.claims.filter((claim: any) => names.some((name) => name.includes(claim.name)));
  expect(submitted).toHaveLength(2);
  expect(new Set(submitted.map((claim: any) => claim.expense_submission_id)).size).toBe(1);
  expect(submitted.map((claim: any) => claim.posting_date).sort()).toEqual([yesterday, today].sort());
  expect(submitted.map((claim: any) => claim.claimed_amount).sort()).toEqual([1, 2]);
});
