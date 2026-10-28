import { expect, test } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

test("Accounts Manager opens Home Chart of Accounts and an account detail", async ({
  page,
}) => {
  await loginViaAPI(
    page.request,
    PERSONAS.accounts.email,
    PERSONAS.accounts.password,
  );
  await page.goto("/volunteering/home");
  const accountsMenu = page.getByRole("navigation", { name: "Sections" }).locator("details").filter({
    has: page.locator("summary").filter({ hasText: /^Accounts$/ }),
  });
  await accountsMenu.locator("summary").click();
  await expect(accountsMenu.getByRole("link", { name: "Chart of Accounts", exact: true })).toBeVisible();
  await accountsMenu.getByRole("link", { name: "Chart of Accounts", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Chart of Accounts" }),
  ).toBeVisible();
  await expect(page.getByText(/^\d+ of \d+ accounts\s*$/)).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);

  const rows = page.locator(".account-row");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThan(0);
  for (const row of await rows.all()) {
    await expect(row).toHaveAttribute("data-account-depth", "0");
  }

  const firstGroup = page
    .locator('.account-row[data-account-depth="0"]:has(.account-toggle)')
    .first();
  await expect(firstGroup).toBeVisible();
  const toggle = firstGroup.locator(".account-toggle");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.locator('.account-row[data-account-depth="1"]').first(),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Add account" })).toBeVisible();
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(
    page.locator('.account-row[data-account-depth="1"]'),
  ).toHaveCount(0);

  await firstGroup.locator(".account-open").click();
  await expect(
    page.getByText("ERPNext protects root accounts from editing or deletion."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Back to chart" }).click();
  await page.locator('select:has(option[value="Ledgers"])').selectOption("Ledgers");
  await page.getByRole("button", { name: /^View ledger for / }).first().click();
  await expect(page.getByRole("heading", { name: "Transactions" })).toBeVisible();
  await expect(page.getByText("Opening balance", { exact: true })).toBeVisible();
  await expect(page.getByText("Closing balance", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit account" })).toBeVisible();
  await page.getByRole("button", { name: "Back to chart" }).click();
  await expect(page.locator('select:has(option[value="Ledgers"])')).toHaveValue("Ledgers");
});

test("ordinary employee cannot open Home Chart of Accounts", async ({
  page,
}) => {
  await loginViaAPI(
    page.request,
    PERSONAS.employee.email,
    PERSONAS.employee.password,
  );
  await page.goto("/volunteering/chart-of-accounts");
  await expect(page.getByRole("alert")).toContainText(
    /Only Accounts Users, Accounts Managers and Administrator/,
  );
  await expect(page.getByRole("button", { name: "Add account" })).toHaveCount(
    0,
  );
});

test("ledger view remains usable on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
  await page.goto("/volunteering/chart-of-accounts");
  await page.locator('select:has(option[value="Ledgers"])').selectOption("Ledgers");
  await page.getByRole("button", { name: /^View ledger for / }).first().click();
  await expect(page.getByRole("heading", { name: "Transactions" })).toBeVisible();
  await expect(page.locator(".ledger-summary")).toBeVisible();
  if (await page.locator(".ledger-mobile-entry").count()) {
    await expect(page.locator(".ledger-mobile-entry").first()).toBeVisible();
    await expect(page.locator(".ledger-table-wrap")).toBeHidden();
  }
  const panelFits = await page.locator(".ledger-panel").evaluate(
    (element) => element.scrollWidth <= element.clientWidth + 1,
  );
  expect(panelFits).toBe(true);
});
