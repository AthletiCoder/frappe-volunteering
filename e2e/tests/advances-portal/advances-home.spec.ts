import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import {
  cleanupEmployeeAdvances,
  e2eCall,
  getCast,
  repairE2eReportsToChain,
} from "../../helpers/e2e-api";
import { PERSONAS, type PersonaKey } from "../../helpers/personas";

const API = "volunteering.volunteering.advance_portal.";
const TEAM = "volunteering.volunteering.team_portal.get_team_dashboard";
const FREEZE = "volunteering.volunteering.advance_freeze.set_advance_freeze";

async function api(page: Page, method: string, args = {}) {
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
      return { status: response.status, data: await response.json() };
    },
    { method, args },
  );
}

async function signIn(page: Page, persona: PersonaKey) {
  await page.context().clearCookies();
  await loginViaAPI(
    page.request,
    PERSONAS[persona].email,
    PERSONAS[persona].password,
  );
  await page.goto("/volunteering/home");
  await expect(page.getByRole("heading", { name: /^Hello/ })).toBeVisible();
}

async function openRequest(page: Page) {
  await page.goto("/volunteering/advances?new=1");
  await expect(
    page.getByRole("heading", { name: "Request an advance", exact: true }),
  ).toBeVisible();
  const response = await api(page, API + "get_advance_request_form");
  expect(response.status).toBe(200);
  const defaults = response.data.message;
  expect(
    defaults.projects.length,
    "Fixture must have active approved project membership",
  ).toBeGreaterThan(0);
  expect(
    defaults.approved_bank,
    "Fixture must have an approved reimbursement bank account",
  ).toBeTruthy();
  return defaults;
}

async function fillRequest(page: Page, amount: number, purpose: string) {
  const defaults = await openRequest(page);
  await page
    .getByRole("combobox", { name: "Intended project *", exact: true })
    .fill("");
  await page
    .getByRole("listbox", { name: "Intended project *", exact: true })
    .getByRole("option")
    .first()
    .click();
  await page
    .getByRole("spinbutton", { name: /Amount \(/ })
    .fill(String(amount));
  await page.getByLabel("Required by *", { exact: true }).fill(defaults.today);
  await page
    .getByLabel("Expected settlement date *", { exact: true })
    .fill(defaults.today);
  await page.getByLabel("Purpose *", { exact: true }).fill(purpose);
  return defaults;
}

async function saveRequest(page: Page, submit: boolean) {
  const saved = page.waitForResponse((response) =>
    response.url().includes(API + "save_advance_request"),
  );
  await page
    .getByRole("button", {
      name: submit ? "Submit for approval" : "Save draft",
      exact: true,
    })
    .click();
  const response = await saved;
  expect(response.status()).toBe(200);
  const result = (await response.json()).message;
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: `Advance ${result.name} saved.` }),
  ).toBeVisible();
  return result;
}

test.beforeEach(async ({ page, request, baseURL }) => {
  if (
    !baseURL ||
    !["127.0.0.1", "localhost", "sevamrita.local"].includes(
      new URL(baseURL).hostname,
    )
  ) {
    throw new Error("Advance portal write tests are restricted to localhost.");
  }
  await repairE2eReportsToChain(request);
  await signIn(page, "employee");
});

test.afterEach(async ({ request }) => {
  const cast = await getCast(request);
  await cleanupEmployeeAdvances(request, cast.employee.employee!);
});

test("AP-001: Home request form exposes scoped projects and masked bank details, not ledger fields", async ({
  page,
}) => {
  await page.getByRole("link", { name: /Request an advance/ }).click();
  await expect(page).toHaveURL(/\/volunteering\/advances\?new=1/);
  const defaults = await openRequest(page);
  for (const internal of [
    /^Series/,
    /^Company/,
    /^Department/,
    /^Advance account/,
    /^Payable account/,
  ]) {
    await expect(page.getByLabel(internal)).toHaveCount(0);
  }
  expect(defaults.approved_bank.account_number).toBe(
    defaults.approved_bank.account_number_masked,
  );
  expect(defaults.approved_bank.account_number).toMatch(/^•+\d{4}$/);
  await expect(
    page.getByText(defaults.approved_bank.account_number_masked, {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("radio", { name: /Team expenses/ }),
  ).toBeDisabled();
  await page.getByRole("combobox", { name: "Intended project *" }).fill("");
  await expect(
    page
      .getByRole("listbox", { name: "Intended project *" })
      .getByRole("option"),
  ).toHaveCount(defaults.projects.length);
});

test("AP-002: Employee saves a private quotation, edits the draft and submits above the former grade cap", async ({
  page,
  request,
}) => {
  const cast = await getCast(request);
  const employee = cast.employee.employee!;
  await cleanupEmployeeAdvances(request, employee);
  try {
    await fillRequest(page, 1000, "Portal quotation and draft test");
    await page.getByLabel(/Estimate \/ quotation \(optional\)/).setInputFiles({
      name: "portal-estimate.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlVAAAAAASUVORK5CYII=",
        "base64",
      ),
    });
    const draft = await saveRequest(page, false);
    expect(draft.workflow_state).toBe("Draft");
    const card = page.locator(`[id="advance-${draft.name}"]`);
    const quote = card.getByRole("link", { name: "View estimate / quotation" });
    await expect(quote).toHaveAttribute("href", /^\/private\/files\//);
    expect(
      (await page.request.get((await quote.getAttribute("href"))!)).status(),
    ).toBe(200);
    await card.getByRole("button", { name: "Edit draft" }).click();
    await expect(
      page.getByRole("heading", { name: `Edit ${draft.name}` }),
    ).toBeVisible();
    await page.getByRole("spinbutton", { name: /Amount \(/ }).fill("6000");
    const submitted = await saveRequest(page, true);
    expect(submitted.name).toBe(draft.name);
    expect(submitted.workflow_state).toBe("Pending Approval");
    await expect(card).toContainText("6,000");
    await expect(card.getByRole("button", { name: "Edit draft" })).toHaveCount(
      0,
    );
  } finally {
    await cleanupEmployeeAdvances(request, employee);
  }
});

test("AP-003: Multiple portal requests are accepted and assigned first to the immediate reporting manager", async ({
  page,
  request,
}) => {
  const cast = await getCast(request);
  const employee = cast.employee.employee!;
  await cleanupEmployeeAdvances(request, employee);
  try {
    await fillRequest(page, 6000, "First concurrent portal request");
    const first = await saveRequest(page, true);
    await fillRequest(page, 5000, "Second concurrent portal request");
    const second = await saveRequest(page, true);
    expect(second.name).not.toBe(first.name);
    await expect(page.locator(`[id="advance-${first.name}"]`)).toContainText(
      "Pending Approval",
    );
    await expect(page.locator(`[id="advance-${second.name}"]`)).toContainText(
      "Pending Approval",
    );
    for (const name of [first.name, second.name]) {
      expect(
        await e2eCall(request, "get_doc_field", {
          doctype: "Employee Advance",
          name,
          field: "pending_approver",
        }),
      ).toBe(cast.manager.email);
    }
  } finally {
    await cleanupEmployeeAdvances(request, employee);
  }
});

test("AP-006: manager decides in Home and Accounts sees the approved advance to disburse", async ({
  page,
  request,
}) => {
  const cast = await getCast(request);
  const employee = cast.employee.employee!;
  await cleanupEmployeeAdvances(request, employee);
  try {
    await fillRequest(page, 500, "Home approval and disbursement queue test");
    await page.getByLabel(/Estimate \/ quotation \(optional\)/).setInputFiles({
      name: "advance-estimate.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlVAAAAAASUVORK5CYII=",
        "base64",
      ),
    });
    const advance = await saveRequest(page, true);

    await signIn(page, "manager");
    await page.goto(`/volunteering/advance-workflow?advance=${advance.name}`);
    await expect(
      page.getByRole("heading", { name: advance.name }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Approval decision" }),
    ).toBeVisible();
    const estimate = page.getByRole("link", {
      name: "Open private estimate / quotation",
    });
    await expect(estimate).toHaveAttribute("href", /^\/private\/files\//);
    expect(
      (await page.request.get((await estimate.getAttribute("href"))!)).status(),
    ).toBe(200);
    await page.getByRole("button", { name: "Approve advance" }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Advance approved" }),
    ).toContainText("Advance approved and sent to Accounts");

    await signIn(page, "accounts");
    await page.goto("/volunteering/advance-workflow?view=disbursement");
    await expect(
      page.getByRole("button", { name: /Accounts disbursement/ }),
    ).toBeVisible();
    await page.getByRole("button", { name: new RegExp(advance.name) }).click();
    await expect(
      page.getByRole("heading", { name: "Accounts disbursement" }),
    ).toBeVisible();
    await expect(
      page.getByRole("spinbutton", { name: "Amount to pay *" }),
    ).toHaveValue("500");
    await expect(
      page.getByRole("button", { name: "Create and submit Payment Entry" }),
    ).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(
      page.getByRole("heading", { name: "Accounts disbursement" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  } finally {
    await cleanupEmployeeAdvances(request, employee);
  }
});

test("AP-007: Accounts disburses and records partial then full unused-advance returns in Home", async ({
  page,
  request,
}, testInfo) => {
  const cast = await getCast(request);
  const employee = cast.employee.employee!;
  await cleanupEmployeeAdvances(request, employee);

  await fillRequest(page, 500, "E2E Home advance return lifecycle");
  const advance = await saveRequest(page, true);
  await testInfo.attach("created-local-advance", {
    body: advance.name,
    contentType: "text/plain",
  });

  await signIn(page, "manager");
  await page.goto(`/volunteering/advance-workflow?advance=${advance.name}`);
  await page.getByRole("button", { name: "Approve advance" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Advance approved" }),
  ).toContainText("Advance approved");

  await signIn(page, "accounts");
  await page.goto(`/volunteering/advance-workflow?advance=${advance.name}`);
  await expect(
    page.getByRole("heading", { name: "Accounts disbursement" }),
  ).toBeVisible();
  await page.getByLabel("Pay from *").selectOption("Cash - SF");
  const sidBeforePayment = (await page.context().cookies()).find(
    (cookie) => cookie.name === "sid",
  )?.value;
  page.once("dialog", (dialog) => dialog.accept());
  const disbursement = page.waitForResponse((response) =>
    response.url().includes("advance_workflow_portal.disburse_advance"),
  );
  await page
    .getByRole("button", { name: "Create and submit Payment Entry" })
    .click();
  const disbursementResult = await disbursement;
  expect(disbursementResult.status(), await disbursementResult.text()).toBe(
    200,
  );
  const paymentName = (await disbursementResult.json()).message.payment_entry;
  const sidAfterPayment = (await page.context().cookies()).find(
    (cookie) => cookie.name === "sid",
  )?.value;
  expect(sidAfterPayment === sidBeforePayment).toBe(true);
  const queueAfterPayment = await api(
    page,
    "volunteering.volunteering.advance_workflow_portal.get_advance_work_queue",
  );
  expect(queueAfterPayment.status).toBe(200);
  expect(
    queueAfterPayment.data.message.queues.return.some(
      (item: any) => item.name === advance.name,
    ),
  ).toBe(true);
  expect(
    await e2eCall(request, "get_doc_field", {
      doctype: "Payment Entry",
      name: paymentName,
      field: "docstatus",
    }),
  ).toBe(1);

  await page.goto("/volunteering/advance-workflow?view=return");
  await expect(
    page.getByRole("button", { name: new RegExp(advance.name) }),
  ).toBeVisible();
  await page.getByRole("button", { name: new RegExp(advance.name) }).click();
  await expect(
    page.getByRole("heading", { name: "Record unused advance returned" }),
  ).toBeVisible();
  await expect(
    page.getByRole("spinbutton", { name: "Amount received *" }),
  ).toHaveValue("500");
  await page.getByRole("spinbutton", { name: "Amount received *" }).fill("300");
  await page.getByLabel("Received into *").selectOption("Cash - SF");
  page.once("dialog", (dialog) => dialog.accept());
  const firstReturn = page.waitForResponse((response) =>
    response.url().includes("advance_workflow_portal.record_advance_return"),
  );
  await page
    .getByRole("button", { name: "Confirm receipt and submit Journal Entry" })
    .click();
  const firstReturnResult = await firstReturn;
  expect(firstReturnResult.status(), await firstReturnResult.text()).toBe(200);
  const first = (await firstReturnResult.json()).message;
  expect(first.returned_amount).toBe(300);
  expect(first.residual_amount).toBe(200);
  expect(
    await e2eCall(request, "get_doc_field", {
      doctype: "Journal Entry",
      name: first.journal_entry,
      field: "docstatus",
    }),
  ).toBe(1);

  await page.goto(`/volunteering/advance-workflow?advance=${advance.name}`);
  await expect(
    page.getByRole("spinbutton", { name: "Amount received *" }),
  ).toHaveValue("200");
  await page.getByLabel("Received into *").selectOption("Cash - SF");
  page.once("dialog", (dialog) => dialog.accept());
  const finalReturn = page.waitForResponse((response) =>
    response.url().includes("advance_workflow_portal.record_advance_return"),
  );
  await page
    .getByRole("button", { name: "Confirm receipt and submit Journal Entry" })
    .click();
  const finalReturnResult = await finalReturn;
  expect(finalReturnResult.status(), await finalReturnResult.text()).toBe(200);
  const final = (await finalReturnResult.json()).message;
  expect(final.returned_amount).toBe(500);
  expect(final.residual_amount).toBe(0);
  await expect(
    page.getByRole("status").filter({ hasText: "Advance return recorded" }),
  ).toContainText("Advance return recorded");
  await expect(
    page.getByRole("button", { name: new RegExp(advance.name) }),
  ).toHaveCount(0);
});

test("AP-004: Direct manager freezes/unfreezes through My team; employee cannot bypass freeze or view another team", async ({
  page,
  browser,
  request,
}) => {
  const cast = await getCast(request);
  const employee = cast.employee.employee!;
  const managerContext = await browser.newContext();
  const managerPage = await managerContext.newPage();
  let changedFreeze = false;
  try {
    await signIn(managerPage, "manager");
    await managerPage
      .getByRole("link", { name: /My team/ })
      .last()
      .click();
    await expect(
      managerPage.getByRole("heading", { name: "My team", exact: true }),
    ).toBeVisible();
    const dashboard = (await api(managerPage, TEAM)).data.message;
    const person = dashboard.team.find((row: any) => row.employee === employee);
    expect(person).toBeTruthy();
    expect(person.advance_control.frozen, "Fixture should begin unfrozen").toBe(
      false,
    );
    for (const sensitive of [
      "bank_ac_no",
      "salary",
      "bank_details",
      "ledger_balance",
    ]) {
      expect(person).not.toHaveProperty(sensitive);
    }
    const card = managerPage.locator("article").filter({
      has: managerPage.getByRole("heading", {
        name: "E2E Employee A",
        exact: true,
      }),
    });
    await expect(card).toContainText("Attendance and requests");
    await card
      .getByLabel("Reason to freeze new advances")
      .fill("Local E2E freeze verification");
    await card.getByRole("button", { name: "Freeze new advances" }).click();
    changedFreeze = true;
    await expect(
      card.getByText("Advances frozen", { exact: true }),
    ).toBeVisible();
    const defaults = await openRequest(page);
    expect(defaults.freeze.frozen).toBe(true);
    await expect(
      page.getByRole("button", { name: "Save draft", exact: true }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Submit for approval", exact: true }),
    ).toBeDisabled();
    const bypass = await api(page, API + "save_advance_request", {
      payload: {
        intended_project: defaults.projects[0].value,
        amount: 1,
        purpose: "Blocked freeze bypass",
        required_by_date: defaults.today,
        expected_settlement_date: defaults.today,
        advance_use: "My expenses",
      },
      submit_request: 1,
    });
    expect(bypass.status).toBe(417);
    expect(JSON.stringify(bypass.data)).toMatch(/frozen/i);
    expect((await api(page, TEAM)).status).toBe(403);
    expect(
      (
        await api(page, FREEZE, {
          employee,
          frozen: 0,
          reason: "Unauthorized self-unfreeze",
        })
      ).status,
    ).toBe(403);
    await card
      .getByLabel("Reason to unfreeze")
      .fill("Local E2E freeze check completed");
    await card.getByRole("button", { name: "Unfreeze advances" }).click();
    await expect(
      card.getByText("Advances frozen", { exact: true }),
    ).toHaveCount(0);
    changedFreeze = false;
    await openRequest(page);
    await expect(
      page.getByRole("button", { name: "Submit for approval", exact: true }),
    ).toBeEnabled();
  } finally {
    if (changedFreeze) {
      const restored = await api(managerPage, FREEZE, {
        employee,
        frozen: 0,
        reason: "Local E2E cleanup",
      });
      expect(restored.status).toBe(200);
    }
    await managerContext.close();
  }
});

test("AP-005: Advance request and team dashboard fit mobile and dark theme", async ({
  page,
  browser,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openRequest(page);
  await expect(
    page.getByRole("button", { name: "Toggle colour theme" }),
  ).toHaveCount(0);
  await page.evaluate(() => localStorage.setItem("volunteering.theme", "dark"));
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  try {
    const managerPage = await context.newPage();
    await signIn(managerPage, "manager");
    await managerPage.goto("/volunteering/team");
    await expect(
      managerPage.getByRole("heading", { name: "My team", exact: true }),
    ).toBeVisible();
    expect(
      await managerPage.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  } finally {
    await context.close();
  }
});
