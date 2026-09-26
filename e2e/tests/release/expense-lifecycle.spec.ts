import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { e2eCall, repairE2eReportsToChain } from "../../helpers/e2e-api";
import { PERSONAS, type PersonaKey } from "../../helpers/personas";

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

test("REL-001: Home claim → receipt reviewer → manager → Accounts classification → cash settlement → Paid", async ({
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

    const reviewer = await reviewerContext.newPage();
    await signIn(reviewer, "receipt_reviewer");
    await reviewer.goto(
      `/volunteering/expense-claim-workflow?claim=${encodeURIComponent(name)}`,
    );
    await expect(reviewer.getByRole("heading", { name })).toBeVisible();
    await expect(reviewer.locator(".check-row")).toHaveCount(0);
    await reviewer
      .getByLabel("Review notes")
      .fill(
        "Local release gate: actual reviewer checked the fictional evidence.",
      );
    await reviewer.getByRole("button", { name: "Verify receipts" }).click();
    await expect(
      reviewer.getByText(
        "Receipts verified; the claim is now with its manager.",
      ),
    ).toBeVisible();
    expect(await field("Expense Claim", name, "receipt_review_status")).toBe(
      "Verified",
    );
    expect(await field("Expense Claim", name, "receipt_reviewed_by")).toBe(
      PERSONAS.receipt_reviewer.email,
    );
    expect(await field("Expense Claim", name, "workflow_state")).toBe(
      "Pending Approval",
    );

    await manager.goto(
      `/volunteering/expense-claim-workflow?claim=${encodeURIComponent(name)}`,
    );
    await expect(manager.getByRole("heading", { name })).toBeVisible();
    const approve = manager.getByRole("button", { name: /^Approve/ });
    await expect(approve).toBeVisible();
    await approve.click();
    await expect(
      manager.getByText(
        "Claim approved by the manager and sent to Accounts for classification.",
      ),
    ).toBeVisible();
    expect(await field("Expense Claim", name, "workflow_state")).toBe(
      "Pending Accounts Classification",
    );
    expect(await field("Expense Claim", name, "docstatus")).toBe(0);
    expect(await field("Expense Claim", name, "total_sanctioned_amount")).toBe(
      1,
    );

    const accounts = await accountsContext.newPage();
    await signIn(accounts, "accounts");
    await accounts.goto(
      `/volunteering/expense-claim-workflow?claim=${encodeURIComponent(name)}`,
    );
    await expect(accounts.getByRole("heading", { name })).toBeVisible();
    await expect(
      accounts.getByRole("heading", { name: "Accounts classification" }),
    ).toBeVisible();
    const classification = accounts
      .getByRole("heading", { name: "Accounts classification" })
      .locator("..");
    const expenseAccount = accounts.getByRole("combobox", {
      name: "Expense account 1",
    });
    if (!(await expenseAccount.inputValue())) {
      await expenseAccount.click();
      await accounts
        .getByRole("listbox", { name: "Expense account 1" })
        .getByRole("option")
        .first()
        .click();
    }
    await classification
      .getByRole("button", { name: "+ Split to another account" })
      .click();
    const secondExpenseAccount = classification.getByRole("combobox", {
      name: "Expense account 2",
    });
    await secondExpenseAccount.click();
    await classification
      .getByRole("listbox", { name: "Expense account 2" })
      .getByRole("option")
      .first()
      .click();
    const allocationAmounts = classification.getByLabel("Amount *");
    await allocationAmounts.nth(0).fill("0.60");
    await allocationAmounts.nth(1).fill("0.40");
    await expect(classification.getByText(/Allocated ₹1\.00 of ₹1\.00/)).toBeVisible();
    accounts.once("dialog", (dialog) => dialog.accept());
    await accounts
      .getByRole("button", { name: "Finalise accounts and submit claim" })
      .click();
    await expect(
      accounts.getByText(
        "Accounts classified and claim submitted. It is now ready for reimbursement.",
      ),
    ).toBeVisible();
    expect(await field("Expense Claim", name, "workflow_state")).toBe(
      "Approved",
    );
    expect(await field("Expense Claim", name, "docstatus")).toBe(1);
    expect(await field("Expense Claim", name, "account_classification_status")).toBe(
      "Complete",
    );
    expect(await field("Expense Claim", name, "status")).toBe("Unpaid");

    await accounts.goto(
      `/volunteering/expense-claim-workflow?claim=${encodeURIComponent(name)}`,
    );
    await expect(accounts.getByRole("heading", { name })).toBeVisible();
    await accounts.getByLabel("Pay from *").selectOption("Cash - SF");
    accounts.once("dialog", (dialog) => dialog.accept());
    const paymentResponse = accounts.waitForResponse((response) =>
      response
        .url()
        .includes("expense_claim_workflow_portal.reimburse_expense_claim"),
    );
    await accounts
      .getByRole("button", { name: "Create and submit Payment Entry" })
      .click();
    const paymentResult = await paymentResponse;
    expect(paymentResult.status(), await paymentResult.text()).toBe(200);
    const paymentName = (await paymentResult.json()).message.payment_entry;
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
    await page.goto(
      `/volunteering/expense-claims?claim=${encodeURIComponent(name)}`,
    );
    await expect(page.getByText("Paid", { exact: true }).first()).toBeVisible();
  } finally {
    await managerContext.close();
    await reviewerContext.close();
    await accountsContext.close();
  }
});
