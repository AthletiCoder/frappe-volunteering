import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

async function workspace(page: Page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/method/volunteering.volunteering.donation_portal.get_donation_workspace", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": (window as any).csrf_token || "" },
      credentials: "same-origin",
      body: "{}",
    });
    if (!response.ok) throw new Error(`Donation workspace failed: ${response.status}`);
    return (await response.json()).message;
  });
}

test.beforeEach(({ baseURL }) => {
  if (!baseURL || !["127.0.0.1", "localhost", "sevamrita.local"].includes(new URL(baseURL).hostname)) {
    throw new Error("Donation regression must run against the local demo site only.");
  }
});

test("only Accounts can list and record donations", async ({ page }) => {
  await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
  await page.goto("/volunteering/donations");
  await expect(
    page.getByRole("heading", { name: "Not Permitted" })
      .or(page.getByRole("alert").filter({ hasText: "Only Accounts Managers" })),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Record a donation" })).toHaveCount(0);

  await page.context().clearCookies();
  await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
  await page.goto("/volunteering/donations");
  await expect(page.getByRole("heading", { name: "Recorded donations" })).toBeVisible();
  await page.getByRole("button", { name: "Record a donation" }).click();
  await expect(page.getByRole("heading", { name: "Donor details" })).toBeVisible();
  await expect(page.getByLabel("PAN *")).toBeVisible();
  await expect(page.getByLabel("Phone number")).not.toHaveAttribute("required", "");
  await expect(page.getByLabel("Donation credit ledger")).toHaveValue(/General Donations/);
  await expect(page.getByRole("button", { name: /CSR donation/ })).toHaveCount(0);
  await expect(page.getByLabel(/Authorised Sevamrita signatory/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Record donation", exact: true })).toBeEnabled();
});

test("record first, then issue a signed private receipt from the list", async ({ page }) => {
  test.skip(process.env.E2E_DONATION_WRITES !== "1", "Opt-in local accounting write.");
  await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
  await page.goto("/volunteering/donations");
  await page.getByRole("button", { name: "Record a donation" }).click();
  let before = await workspace(page);
  expect(before.accounts.donation_credit_by_type.General?.name).toBeTruthy();
  const donorName = `Local general regression ${Date.now()}`;
  const pan = `TSTAB${String(Date.now() % 10000).padStart(4, "0")}F`;
  await page.getByLabel("Donor name *").fill(donorName);
  await page.getByLabel("PAN *").fill(pan);
  await page.getByLabel("Full postal address *").fill("2 Local Test Street, Mumbai, Maharashtra 400001");
  await page.getByLabel("Amount received (INR) *").fill("12");
  await page.getByLabel("Payment method *").selectOption("Bank Transfer");
  await page.getByLabel("Cheque / transaction reference *").fill(`GEN-LOCAL-${Date.now()}`);
  const bank = before.accounts.received_into.find((account: any) => account.account_type === "Bank");
  expect(bank?.name).toBeTruthy();
  await page.getByLabel("Money received into *").selectOption(bank.name);
  await page.getByRole("button", { name: "Record donation", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Donation recorded" })).toContainText("Receipt pending");
  await expect(page.getByLabel("Receipt status")).toHaveValue("pending");
  const pendingRow = page.locator("article").filter({ hasText: donorName });
  await expect(pendingRow).toContainText("Pending receipt");
  const posted = (await workspace(page)).history.find((row: any) => row.full_name === donorName);
  expect(posted?.journal_entry).toBeTruthy();
  expect(posted?.receipt_number).toBeFalsy();

  await page.getByRole("button", { name: "Receipt setup", exact: true }).click();
  if (!before.settings.registered_address || !before.settings.contact_email || !before.settings.organisation_name) {
    const setup = page.locator("details.setup-card").filter({ has: page.locator("summary").filter({ hasText: "Receipt identity and registration" }) });
    await setup.locator("summary").click();
    await setup.getByLabel("Organisation name *").fill(before.settings.organisation_name || "LOCAL TEST ORGANISATION");
    await setup.getByLabel("Contact email *").fill(before.settings.contact_email || "local-test@example.invalid");
    await setup.getByLabel("Registered office address *").fill(before.settings.registered_address || "LOCAL TEST ADDRESS — NOT FOR EXTERNAL USE");
    await setup.getByRole("button", { name: "Save receipt details" }).click();
    await expect(page.getByRole("status")).toContainText("Receipt identity saved");
    before = await workspace(page);
  }
  if (!before.signatories.length) {
    const setup = page.locator("details.setup-card").filter({ has: page.locator("summary").filter({ hasText: "Register an authorised signature" }) });
    await setup.locator("summary").click();
    await setup.getByLabel("Signatory name *").fill("LOCAL TEST SIGNATORY — NOT VALID");
    await setup.getByLabel("Designation").fill("Test automation only");
    await setup.getByRole("button", { name: "Draw signature" }).click();
    const canvas = page.getByRole("dialog", { name: "Draw signature" }).locator("canvas");
    const box = await canvas.boundingBox();
    expect(box).toBeTruthy();
    await page.mouse.move(box!.x + 30, box!.y + 40);
    await page.mouse.down();
    await page.mouse.move(box!.x + 100, box!.y + 70);
    await page.mouse.up();
    await page.getByRole("button", { name: "Use signature" }).click();
    await setup.getByRole("button", { name: "Save signatory" }).click();
    await expect(page.getByRole("status")).toContainText("Authorised signature registered");
    before = await workspace(page);
  }
  expect(before.signatories.length).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Donations list", exact: true }).click();
  await pendingRow.getByRole("button", { name: "Issue receipt", exact: true }).click();
  await pendingRow.getByLabel("Authorised Sevamrita signatory *").selectOption(before.signatories[0].name);
  await pendingRow.getByRole("button", { name: "Issue signed PDF" }).click();
  await expect(page.getByRole("status").filter({ hasText: /Receipt RE-/ })).toContainText("issued");
  await page.getByLabel("Receipt status").selectOption("issued");
  const receiptLink = pendingRow.getByRole("link", { name: /Open PDF/ });
  await expect(receiptLink).toHaveAttribute("href", /^\/private\/files\//);
  const receipt = await page.request.get((await receiptLink.getAttribute("href"))!);
  expect(receipt.ok()).toBeTruthy();
  expect((await receipt.body()).subarray(0, 4).toString()).toBe("%PDF");
  const recorded = (await workspace(page)).history.find((row: any) => row.name === posted.name);
  expect(recorded?.donation_purpose).toBe("General");
  expect(recorded?.receipt_number).toBeTruthy();
  expect(recorded?.journal_entry).toBe(posted.journal_entry);
});
