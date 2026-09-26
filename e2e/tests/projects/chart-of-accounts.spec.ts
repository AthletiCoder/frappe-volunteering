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
  await expect(
    page.getByRole("link", { name: /Chart of Accounts/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: /Chart of Accounts/ }).click();
  await expect(
    page.getByRole("heading", { name: "Chart of Accounts" }),
  ).toBeVisible();
  await expect(page.getByText(/of .* accounts/)).toBeVisible();
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
    /Only Accounts Managers and Administrator/,
  );
  await expect(page.getByRole("button", { name: "Add account" })).toHaveCount(
    0,
  );
});
