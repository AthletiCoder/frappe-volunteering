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
  await page.locator(".account-row").first().click();
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
