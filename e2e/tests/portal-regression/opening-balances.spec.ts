import { expect, test } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

test("Accounts Manager can prepare an opening balance with a balanced preview", async ({ page }) => {
  await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
  await page.goto("/volunteering/opening-balances");

  await expect(page.getByRole("heading", { name: "Opening balances", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Record a starting balance" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);

  const account = page.getByRole("combobox", { name: "Ledger account *" });
  await account.click();
  await page.getByRole("listbox", { name: "Ledger account *" }).getByRole("option").first().click();
  await page.getByRole("spinbutton", { name: /Amount \(.*\) \*/ }).fill("500");
  await page.getByRole("textbox", { name: "Source reference *" }).fill("Release test opening record");

  const preview = page.locator(".posting-preview");
  await expect(preview).toBeVisible();
  await expect(preview.locator(".preview-row")).toHaveCount(2);
  await expect(preview).toContainText("Temporary Opening");
  await expect(page.getByRole("button", { name: "Post opening balance" })).toBeVisible();
});

test("ordinary employee cannot access opening balances", async ({ page }) => {
  await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
  await page.goto("/volunteering/opening-balances");
  await expect(page.getByRole("alert")).toContainText(/Accounts Manager|Administrator/);
  await expect(page.getByRole("button", { name: "Post opening balance" })).toHaveCount(0);
});
