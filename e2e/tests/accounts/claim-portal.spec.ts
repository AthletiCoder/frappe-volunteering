import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

const API = "volunteering.volunteering.expense_claim_portal.";

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
      if (!response.ok) throw new Error(await response.text());
      return (await response.json()).message;
    },
    { method, args },
  );
}

test.describe("Employee expense portal @ui @expense-portal", () => {
  test.beforeEach(async ({ page, baseURL }) => {
    if (
      !baseURL ||
      !["127.0.0.1", "localhost", "sevamrita.local"].includes(
        new URL(baseURL).hostname,
      )
    ) {
      throw new Error("Expense portal demo tests are restricted to localhost.");
    }
    await page.context().clearCookies();
    await loginViaAPI(
      page.request,
      PERSONAS.employee.email,
      PERSONAS.employee.password,
    );
    await page.goto("/volunteering/home");
    await expect(page.getByRole("heading", { name: /^Hello/ })).toBeVisible();
    await page.getByRole("link", { name: /Submit an Expense/ }).click();
    await expect(
      page.getByRole("heading", { name: "Submit an expense", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("combobox", { name: "Project *", exact: true }),
    ).toBeVisible();
  });

  test("Home opens the portal; only safe project account choices and employee fields appear", async ({
    page,
  }) => {
    await expect(page).toHaveURL(/\/volunteering\/expense-claim$/);
    for (const field of [
      /^Series/,
      /^Company/,
      /^Department/,
      /^Cost Cent[er]{2}/,
      /^Payable/,
      /^Sanctioned/,
    ]) {
      await expect(page.getByLabel(field)).toHaveCount(0);
    }
    const defaults = await api(page, API + "get_expense_claim_form");
    expect(defaults.projects.length).toBeGreaterThan(0);
    const project = defaults.projects[0].value;
    await page
      .getByRole("combobox", { name: "Project *", exact: true })
      .selectOption(project);
    const accounts = await api(page, API + "get_project_accounts", { project });
    const accountInput = page.getByRole("combobox", {
      name: "Project expense account *",
      exact: true,
    });
    await expect(accountInput).toBeEnabled();
    await accountInput.fill("");
    const menu = page.getByRole("listbox", {
      name: "Project expense account *",
      exact: true,
    });
    await expect(menu.getByRole("option")).toHaveCount(accounts.length);
    expect(
      accounts.every(
        (row: any) => !("balance" in row) && !("approved_amount" in row),
      ),
    ).toBeTruthy();
    await menu.getByRole("option").first().click();
    await expect(accountInput).toHaveValue(accounts[0].label);
    await page.getByRole("button", { name: "+ Add expense item" }).click();
    await expect(
      page.getByRole("heading", { name: "Expense item 2", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("article")
      .last()
      .getByRole("button", { name: "Remove", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Expense item 2", exact: true }),
    ).toHaveCount(0);
    await page.getByLabel("This was an emergency expense").check();
    await expect(
      page.getByLabel("Emergency date *", { exact: true }),
    ).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: "test-results/expense-portal/employee-form.png",
      fullPage: true,
    });
  });

  test("the form fits a mobile viewport and supports dark theme", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(
      page.getByRole("heading", { name: "Claim context", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page.getByRole("button", { name: "Toggle colour theme" }).click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect.poll(() => page.getByRole("button", { name: /^Against manager/ }).evaluate(
      (button) => getComputedStyle(button).backgroundColor,
    )).toBe("rgb(18, 17, 16)");
    await expect(page.locator(".form-grid")).toHaveCount(0);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: "test-results/expense-portal/mobile-form.png",
      fullPage: true,
    });
  });

  test("browser submission attaches the item receipt and enters receipt review", async ({
    page,
  }) => {
    test.skip(
      process.env.E2E_EXPENSE_PORTAL_WRITES !== "1",
      "Opt-in submission creates a local demo claim.",
    );
    const defaults = await api(page, API + "get_expense_claim_form");
    await page
      .getByRole("combobox", { name: "Project *", exact: true })
      .selectOption(defaults.projects[0].value);
    await page
      .getByRole("combobox", { name: "Project expense account *", exact: true })
      .click();
    await page
      .getByRole("listbox", { name: "Project expense account *", exact: true })
      .getByRole("option")
      .first()
      .click();
    await page
      .getByLabel("Purpose of this claim *", { exact: true })
      .fill("Local browser test of the employee Expense Claim form");
    await page
      .getByLabel("Supplier / payee", { exact: true })
      .fill("Local demo supplier");
    await page
      .getByLabel("Receipt / invoice number", { exact: true })
      .fill(`PORTAL-DEMO-${Date.now()}`);
    await page
      .getByLabel("Description and business purpose *", { exact: true })
      .fill("Fictional local test purchase, no real payment");
    await page.getByLabel(/^Amount \(/).fill("1");
    await page.getByLabel("Receipt evidence *", { exact: true }).setInputFiles({
      name: "local-demo-receipt.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlVAAAAAASUVORK5CYII=",
        "base64",
      ),
    });
    await page
      .getByRole("button", { name: "Submit for receipt review", exact: true })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Sent for receipt review",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.locator("strong").filter({ hasText: /^HR-EXP-/ }),
    ).toBeVisible();
    await page.screenshot({
      path: "test-results/expense-portal/submitted-claim.png",
      fullPage: true,
    });
  });
});
