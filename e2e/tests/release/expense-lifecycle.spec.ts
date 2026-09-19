import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { e2eCall, repairE2eReportsToChain } from "../../helpers/e2e-api";
import { PERSONAS, type PersonaKey } from "../../helpers/personas";
import { ExpenseClaimFormPage } from "../../pages/desk/expense-claim.page";
import { DeskForm } from "../../helpers/desk";

async function signIn(page: Page, persona: PersonaKey) {
  await loginViaAPI(
    page.request,
    PERSONAS[persona].email,
    PERSONAS[persona].password,
  );
  await page.goto("/volunteering/home");
  await expect(page.getByRole("heading", { name: /^Hello/ })).toBeVisible();
}

async function portalData(page: Page, method: string, args = {}) {
  return page.evaluate(
    async ({ method, args }) => {
      const response = await fetch(`/api/method/${method}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Frappe-CSRF-Token": (window as any).csrf_token || "",
        },
        body: JSON.stringify(args),
      });
      if (!response.ok)
        throw new Error(`${response.status()}: ${await response.text()}`);
      return (await response.json()).message;
    },
    { method, args },
  );
}

test("REL-001: Home claim → actual receipt reviewer → manager → cash settlement → Paid", async ({
  page,
  browser,
  request,
  baseURL,
}, testInfo) => {
  // This deliberately exercises five real UI sessions and the complete
  // accounting lifecycle, so it needs more than the suite's default timeout.
  test.setTimeout(240_000);
  if (
    !baseURL ||
    !["127.0.0.1", "localhost", "sevamrita.local"].includes(
      new URL(baseURL).hostname,
    )
  ) {
    throw new Error("Fictional payment lifecycle is restricted to localhost.");
  }
  await repairE2eReportsToChain(request);
  await signIn(page, "employee");
  await page.getByRole("link", { name: /Submit an Expense/ }).click();
  const defaults = await portalData(
    page,
    "volunteering.volunteering.expense_claim_portal.get_expense_claim_form",
  );
  expect(defaults.projects.length).toBeGreaterThan(0);
  let mappedProject = "";
  for (const candidate of defaults.projects) {
    const categories = await portalData(
      page,
      "volunteering.volunteering.expense_claim_portal.get_project_accounts",
      { project: candidate.value },
    );
    // A newly approved proposal intentionally awaits Accounts Manager mapping.
    if (categories.length) {
      mappedProject = candidate.value;
      break;
    }
  }
  expect(
    mappedProject,
    "Local fixture must include a mapped claimable project",
  ).toBeTruthy();
  await page
    .getByRole("combobox", { name: "Project *", exact: true })
    .selectOption(mappedProject);
  await page
    .getByRole("combobox", { name: "Project expense category *", exact: true })
    .click();
  await page
    .getByRole("listbox", { name: "Project expense category *", exact: true })
    .getByRole("option")
    .first()
    .click();
  await page
    .getByLabel("Purpose of this claim *", { exact: true })
    .fill("Local release gate: fictional ₹1 expense");
  await page
    .getByLabel("Supplier / payee", { exact: true })
    .fill("Fictional local QA supplier");
  await page
    .getByLabel("Receipt / invoice number", { exact: true })
    .fill(`RELEASE-QA-${Date.now()}`);
  await page
    .getByLabel("Description and business purpose *", { exact: true })
    .fill("Fictional QA receipt; no real purchase or bank transfer");
  await page.getByLabel(/^Amount \(/).fill("1");
  await page.getByLabel("Receipt evidence *", { exact: true }).setInputFiles({
    name: "release-qa-receipt.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlVAAAAAASUVORK5CYII=",
      "base64",
    ),
  });
  const submitted = page.waitForResponse((response) =>
    response.url().includes("expense_claim_portal.submit_expense_claim"),
  );
  await page
    .getByRole("button", { name: "Submit for receipt review", exact: true })
    .click();
  const response = await submitted;
  expect(response.status(), await response.text()).toBe(200);
  const created = (await response.json()).message;
  const name = created.name;
  expect(name).toMatch(/^HR-EXP-/);
  await expect(
    page.getByRole("heading", { name: "Sent for receipt review", exact: true }),
  ).toBeVisible();
  await testInfo.attach("created-local-claim", {
    body: JSON.stringify(created, null, 2),
    contentType: "application/json",
  });
  const field = (doctype: string, docname: string, key: string) =>
    e2eCall<any>(request, "get_doc_field", {
      doctype,
      name: docname,
      field: key,
    });
  expect(await field("Expense Claim", name, "workflow_state")).toBe(
    "Pending Receipt Review",
  );

  const managerContext = await browser.newContext();
  const reviewerContext = await browser.newContext();
  const accountsContext = await browser.newContext();
  try {
    const manager = await managerContext.newPage();
    await signIn(manager, "manager");
    const managerClaim = new ExpenseClaimFormPage(manager);
    await managerClaim.open(name);
    await expect(
      manager
        .locator(".primary-action:visible")
        .filter({ hasText: /^Approve$/ }),
    ).toHaveCount(0);

    const reviewer = await reviewerContext.newPage();
    await signIn(reviewer, "receipt_reviewer");
    const reviewedClaim = new ExpenseClaimFormPage(reviewer);
    await reviewedClaim.open(name);
    await reviewedClaim.verifyReceipts(
      "Local release gate: actual reviewer checked the fictional evidence.",
    );
    expect(await field("Expense Claim", name, "receipt_review_status")).toBe(
      "Verified",
    );
    expect(await field("Expense Claim", name, "receipt_reviewed_by")).toBe(
      PERSONAS.receipt_reviewer.email,
    );
    expect(await field("Expense Claim", name, "workflow_state")).toBe(
      "Pending Approval",
    );

    await managerClaim.open(name);
    // No API bypass: the real manager Approve button must be available.
    const approve = manager
      .locator(".primary-action:visible")
      .filter({ hasText: /^Approve$/ })
      .first();
    await expect(approve).toBeVisible();
    await managerClaim.clickWorkflowAction("Approve", { allowConfirm: true });
    expect(await field("Expense Claim", name, "workflow_state")).toBe(
      "Approved",
    );
    expect(await field("Expense Claim", name, "docstatus")).toBe(1);
    expect(await field("Expense Claim", name, "total_sanctioned_amount")).toBe(
      1,
    );
    expect(await field("Expense Claim", name, "status")).toBe("Unpaid");

    const accounts = await accountsContext.newPage();
    await signIn(accounts, "accounts");
    await new ExpenseClaimFormPage(accounts).open(name);
    const menu = accounts
      .locator('.inner-group-button[data-label="Create"] > button')
      .first();
    await expect(menu).toBeVisible();
    await menu.click();
    await accounts
      .locator(".dropdown-menu:visible")
      .getByText("Payment", { exact: true })
      .click();
    await expect(accounts).toHaveURL(/\/desk\/payment-entry\/new-/);
    await accounts.waitForFunction(
      () =>
        (window as any).cur_frm?.doctype === "Payment Entry" &&
        (window as any).cur_frm?.doc?.party,
    );
    // Use a local cash ledger, never bank integration or external remittance.
    await accounts.evaluate(async () => {
      await (window as any).cur_frm.set_value("paid_from", "Cash - SF");
    });
    const payment = new DeskForm(accounts);
    const saveResponse = accounts.waitForResponse((r) =>
      r.url().includes("frappe.desk.form.save.savedocs"),
    );
    await payment.clickPrimary("Save", { allowConfirm: true });
    const saved = await saveResponse;
    expect(saved.status(), await saved.text()).toBe(200);
    await expect(accounts).toHaveURL(/\/desk\/payment-entry\/ACC-PAY-/);
    const paymentName = await accounts.evaluate(
      () => (window as any).cur_frm.doc.name,
    );
    await payment.clickPrimary("Submit", { allowConfirm: true });
    await expect
      .poll(() => field("Payment Entry", paymentName, "docstatus"))
      .toBe(1);
    await expect
      .poll(() => field("Expense Claim", name, "status"))
      .toBe("Paid");
    expect(await field("Expense Claim", name, "total_amount_reimbursed")).toBe(
      1,
    );
    await testInfo.attach("local-payment", {
      body: JSON.stringify({
        claim: name,
        payment: paymentName,
        source: "Cash - SF",
        amount: 1,
      }),
      contentType: "application/json",
    });
    await new ExpenseClaimFormPage(page).open(name);
    await page.waitForFunction(
      () => (window as any).cur_frm?.doc?.status === "Paid",
    );
  } finally {
    await managerContext.close();
    await reviewerContext.close();
    await accountsContext.close();
  }
});
