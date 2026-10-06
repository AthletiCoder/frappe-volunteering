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

test("only Accounts can open donations; type controls fields, ledger and receipt", async ({ page }) => {
  await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
  await page.goto("/volunteering/donations");
  await expect(page.getByRole("heading", { name: "Register a donation" })).toBeVisible();
  await expect(page.getByRole("button", { name: "General donation" })).toHaveCount(0);

  await page.context().clearCookies();
  await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
  await page.goto("/volunteering/donations");
  await expect(page.getByRole("button", { name: /General donation/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /CSR donation/ })).toBeVisible();
  await page.getByRole("button", { name: /CSR donation/ }).click();
  await expect(page.getByRole("heading", { name: "CSR organisation" })).toBeVisible();
  await expect(page.getByLabel("PAN *")).toBeVisible();
  await expect(page.getByLabel("Phone number")).not.toHaveAttribute("required", "");
  await expect(page.getByLabel("Donation credit ledger")).toHaveValue(/CSR Grants/);
  await expect(page.getByRole("button", { name: "Record CSR donation" })).toBeVisible();
  await expect(page.getByLabel(/Authorised Sevamrita signatory/)).toHaveCount(0);
  await page.getByRole("button", { name: /General donation/ }).click();
  await expect(page.getByRole("heading", { name: "Donor details" })).toBeVisible();
  await expect(page.getByLabel("Phone number *")).toBeVisible();
  await expect(page.getByLabel("Donation credit ledger")).toHaveValue(/General Donations/);
  await expect(page.getByLabel(/Authorised Sevamrita signatory/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Record donation and issue receipt" })).toBeVisible();
});

test("CSR posts without a receipt and its donor can be reused", async ({ page }) => {
  test.skip(process.env.E2E_DONATION_WRITES !== "1", "Opt-in local accounting write.");
  await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
  await page.goto("/volunteering/donations");
  await page.getByRole("button", { name: /CSR donation/ }).click();
  const before = await workspace(page);
  expect(before.accounts.donation_credit_by_type.CSR?.name).toBeTruthy();
  expect(before.accounts.received_into.length).toBeGreaterThan(0);
  const donorName = `Local CSR regression ${Date.now()}`;
  const pan = `TSTAA${String(Date.now() % 10000).padStart(4, "0")}F`;
  await page.getByLabel("Donor name *").fill(donorName);
  await page.getByLabel("PAN *").fill(pan);
  await page.getByLabel("Full postal address *").fill("1 Local Test Street, Pune, Maharashtra 411001");
  await page.getByLabel("Amount received (INR) *").fill("11");
  await page.getByLabel("Payment method *").selectOption("Bank Transfer");
  await page.getByLabel("Cheque / transaction reference *").fill(`CSR-LOCAL-${Date.now()}`);
  const bank = before.accounts.received_into.find((account: any) => account.account_type === "Bank");
  expect(bank?.name).toBeTruthy();
  await page.getByLabel("Money received into *").selectOption(bank.name);
  await page.getByRole("button", { name: "Record CSR donation" }).click();
  await expect(page.getByRole("status")).toContainText("CSR donation recorded without a receipt");
  await expect(page.getByText("CSR donation recorded", { exact: true })).toBeVisible();
  const after = await workspace(page);
  const saved = after.donors.find((donor: any) => donor.donor_name === donorName);
  expect(saved?.name).toBeTruthy();
  await page.getByLabel("Donor name *").fill(`${saved.donor_name} · ${saved.name}`);
  await expect(page.getByLabel("PAN *")).toHaveValue(pan);
  await expect(page.getByLabel("Full postal address *")).toHaveValue("1 Local Test Street, Pune, Maharashtra 411001");
  const recorded = after.history.find((row: any) => row.full_name === donorName);
  expect(recorded?.donation_purpose).toBe("CSR");
  expect(recorded?.receipt_file).toBeFalsy();
  expect(recorded?.journal_entry).toBeTruthy();
});

test("general donation requires phone and produces a signed private receipt", async ({ page }) => {
  test.skip(process.env.E2E_DONATION_WRITES !== "1", "Opt-in local accounting write.");
  await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
  await page.goto("/volunteering/donations");
  await page.getByRole("button", { name: /General donation/ }).click();
  let before = await workspace(page);
  expect(before.accounts.donation_credit_by_type.General?.name).toBeTruthy();
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
  const donorName = `Local general regression ${Date.now()}`;
  const pan = `TSTAB${String(Date.now() % 10000).padStart(4, "0")}F`;
  await page.getByLabel("Donor name *").fill(donorName);
  await page.getByLabel("PAN *").fill(pan);
  await page.getByLabel("Full postal address *").fill("2 Local Test Street, Mumbai, Maharashtra 400001");
  await page.getByLabel("Phone number *").fill("9000000000");
  await page.getByLabel("Amount received (INR) *").fill("12");
  await page.getByLabel("Payment method *").selectOption("Bank Transfer");
  await page.getByLabel("Cheque / transaction reference *").fill(`GEN-LOCAL-${Date.now()}`);
  const bank = before.accounts.received_into.find((account: any) => account.account_type === "Bank");
  expect(bank?.name).toBeTruthy();
  await page.getByLabel("Money received into *").selectOption(bank.name);
  await page.getByLabel("Authorised Sevamrita signatory *").selectOption(before.signatories[0].name);
  await page.getByRole("button", { name: "Record donation and issue receipt" }).click();
  await expect(page.getByRole("status")).toContainText(/Donation recorded\. Receipt/);
  const after = await workspace(page);
  const recorded = after.history.find((row: any) => row.full_name === donorName);
  expect(recorded?.donation_purpose).toBe("General");
  expect(recorded?.receipt_number).toBeTruthy();
  expect(recorded?.receipt_file).toMatch(/^\/private\/files\//);
  expect(recorded?.journal_entry).toBeTruthy();
});
