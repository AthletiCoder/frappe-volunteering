import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI, isLoggedIn } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

const METHOD = "volunteering.volunteering.employee_profile.get_my_profile";

async function readProfile(page: Page, args = {}) {
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
    { method: METHOD, args },
  );
}

test.beforeEach(async ({ page, baseURL }) => {
  if (
    !baseURL ||
    !["127.0.0.1", "localhost", "sevamrita.local"].includes(
      new URL(baseURL).hostname,
    )
  ) {
    throw new Error("Profile demo tests are restricted to localhost.");
  }
  await loginViaAPI(
    page.request,
    PERSONAS.employee.email,
    PERSONAS.employee.password,
  );
  await page.goto("/volunteering/home");
  await expect(page.getByRole("heading", { name: /^Hello/ })).toBeVisible();
});

test("Home opens a read-only own profile; supplied identities cannot expose another employee", async ({
  page,
}) => {
  const own = await readProfile(page);
  expect(own.account.user_id).toBe(PERSONAS.employee.email);
  expect(own.employee.name).toBeTruthy();
  await page.screenshot({
    path: "test-results/profile/home-buttons.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await expect(page).toHaveURL(/\/volunteering\/profile$/);
  await expect(
    page.getByRole("heading", { name: "My profile", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(own.employee.name, { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Contact details", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator("input, select, textarea, [contenteditable='true']"),
  ).toHaveCount(0);
  for (const sensitive of [
    "bank_ac_no",
    "pan_number",
    "salary",
    "reset_password_key",
  ]) {
    expect(own.employee).not.toHaveProperty(sensitive);
    expect(own.account).not.toHaveProperty(sensitive);
  }
  const injected = await readProfile(page, {
    employee: "OTHER-EMPLOYEE",
    user: PERSONAS.employee_b.email,
  });
  expect(injected).toEqual(own);
  await page.reload();
  await expect(
    page.getByText(own.employee.name, { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/profile/employee-profile.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Back to Home", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Logout", exact: true }),
  ).toBeVisible();
});

test("A second employee sees their own record, not the first employee's", async ({
  page,
}) => {
  const first = await readProfile(page);
  await page.context().clearCookies();
  await loginViaAPI(
    page.request,
    PERSONAS.employee_b.email,
    PERSONAS.employee_b.password,
  );
  await page.goto("/volunteering/profile");
  await expect(
    page.getByRole("heading", { name: "Employment details", exact: true }),
  ).toBeVisible();
  const second = await readProfile(page);
  expect(second.account.user_id).toBe(PERSONAS.employee_b.email);
  expect(second.employee.name).not.toBe(first.employee.name);
  await expect(
    page.getByText(second.employee.name, { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(first.employee.name, { exact: true }),
  ).toHaveCount(0);
});

test("Home and profile fit mobile and enforce light theme", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("link", { name: "Profile", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Logout", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Employment details", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Toggle colour theme" }),
  ).toHaveCount(0);
  await page.evaluate(() => localStorage.setItem("volunteering.theme", "dark"));
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem("volunteering.theme")),
    )
    .toBe("light");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/profile/mobile-profile.png",
    fullPage: true,
  });
});

test("Logout ends the session and protected profile is inaccessible afterwards", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Logout", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);
  expect(await isLoggedIn(page.request)).toBe(false);
  const response = await page.request.post(`/api/method/${METHOD}`, {
    data: {},
  });
  expect(response.status()).toBe(403);
  await page.goto("/volunteering/profile");
  await expect(page).toHaveURL(/\/login/);
  await expect(
    page.getByRole("heading", { name: "My profile", exact: true }),
  ).toHaveCount(0);
});

test("Failed logout shows an error and retains the authenticated Home", async ({
  page,
}) => {
  await page.route("**/api/method/logout", (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ exception: "Logout unavailable. Try again." }),
    }),
  );
  await page.getByRole("button", { name: "Logout", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Logout unavailable. Try again.",
  );
  await expect(
    page.getByRole("button", { name: "Logout", exact: true }),
  ).toBeEnabled();
  await expect(page).toHaveURL(/\/volunteering\/home$/);
  expect(await isLoggedIn(page.request)).toBe(true);
});
