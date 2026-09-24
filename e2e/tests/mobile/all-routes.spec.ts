import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

const projectProposer = {
  email: "demo.project.user@sevamrita.local",
  password: process.env.E2E_PROJECT_PASSWORD || PERSONAS.employee.password,
};
const projectManager = {
  email: "demo.project.manager@sevamrita.local",
  password: process.env.E2E_PROJECT_PASSWORD || PERSONAS.employee.password,
};

async function signIn(page: Page, user: { email: string; password: string }) {
  await page.context().clearCookies();
  await loginViaAPI(page.request, user.email, user.password);
}

async function openRoute(
  page: Page,
  user: { email: string; password: string },
  route: string,
  ready: RegExp | string,
) {
  await signIn(page, user);
  await page.goto(route);
  await expect(page.locator("#app")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: ready }).first(),
  ).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect(
    page
      .locator("main")
      .getByText(/^(Loading|Loading…|Loading\.\.\.)$/)
      .first(),
  ).toBeHidden({ timeout: 10000 });
}

async function auditMobileLayout(
  page: Page,
  testInfo: TestInfo,
  label: string,
) {
  await expect(page.locator('nav[aria-label="Mobile"]')).toBeVisible();
  const audit = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const visible = (element: Element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        rect.width > 0 &&
        rect.height > 0
      );
    };
    const describe = (element: Element) => {
      const html = element as HTMLElement;
      return `${element.tagName.toLowerCase()}${html.id ? `#${html.id}` : ""}${
        html.className && typeof html.className === "string"
          ? `.${html.className.trim().split(/\s+/).slice(0, 3).join(".")}`
          : ""
      }`;
    };
    const clippedControls = Array.from(
      document.querySelectorAll(
        "main button, main a, main input, main select, main textarea, main summary, main canvas",
      ),
    )
      .filter(visible)
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left < -1 || rect.right > viewportWidth + 1;
      })
      .map(describe);
    const smallPrimaryTargets = Array.from(
      document.querySelectorAll(
        "main button.btn-primary, main button.btn-secondary, main a.btn-primary, main a.btn-secondary, main summary",
      ),
    )
      .filter(visible)
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.width < 32 || rect.height < 32;
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return `${describe(element)} (${Math.round(rect.width)}x${Math.round(rect.height)})`;
      });
    const undersizedTextInputs = Array.from(
      document.querySelectorAll(
        'main input:not([type="checkbox"]):not([type="radio"]):not([type="file"]), main select, main textarea',
      ),
    )
      .filter(visible)
      .filter(
        (element) => Number.parseFloat(getComputedStyle(element).fontSize) < 16,
      )
      .map(
        (element) =>
          `${describe(element)} (${getComputedStyle(element).fontSize})`,
      );
    return {
      viewportWidth,
      documentWidth: document.documentElement.scrollWidth,
      clippedControls,
      smallPrimaryTargets,
      undersizedTextInputs,
    };
  });
  expect(
    audit.documentWidth,
    `${label}: document is wider than its phone viewport`,
  ).toBeLessThanOrEqual(audit.viewportWidth + 1);
  expect(
    audit.clippedControls,
    `${label}: interactive controls are clipped`,
  ).toEqual([]);
  expect(
    audit.smallPrimaryTargets,
    `${label}: primary touch targets are smaller than 32px`,
  ).toEqual([]);
  expect(
    audit.undersizedTextInputs,
    `${label}: text fields below 16px can trigger iOS focus zoom`,
  ).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath(`${label}.png`),
    fullPage: true,
  });
}

test.beforeEach(async ({ baseURL }) => {
  if (
    !baseURL ||
    !["127.0.0.1", "localhost", "sevamrita.local"].includes(
      new URL(baseURL).hostname,
    )
  ) {
    throw new Error(
      "The complete mobile audit may only run against localhost.",
    );
  }
});

test("employee Home, Profile and Waiting screens", async ({
  page,
}, testInfo) => {
  for (const screen of [
    { route: "/volunteering/home", ready: /^Hello/, label: "home" },
    { route: "/volunteering/profile", ready: "My profile", label: "profile" },
    { route: "/volunteering/todos", ready: "Waiting", label: "waiting" },
  ]) {
    await test.step(screen.label, async () => {
      await openRoute(page, PERSONAS.employee, screen.route, screen.ready);
      await auditMobileLayout(page, testInfo, screen.label);
    });
  }
});

test("advance list, request form and Team dashboard", async ({
  page,
}, testInfo) => {
  await test.step("advances", async () => {
    await openRoute(
      page,
      PERSONAS.employee,
      "/volunteering/advances",
      "Advances",
    );
    await auditMobileLayout(page, testInfo, "advances");
    await page.getByRole("button", { name: "Request an advance" }).click();
    await expect(
      page.getByRole("heading", { name: "Request an advance" }),
    ).toBeVisible();
    await auditMobileLayout(page, testInfo, "advance-request");
  });
  await test.step("team", async () => {
    await openRoute(page, PERSONAS.manager, "/volunteering/team", "My team");
    await auditMobileLayout(page, testInfo, "team");
  });
});

test("expense claim and invoice preparation forms", async ({
  page,
}, testInfo) => {
  await test.step("expense-claim", async () => {
    await openRoute(
      page,
      PERSONAS.employee,
      "/volunteering/expense-claim",
      "Submit an expense",
    );
    await auditMobileLayout(page, testInfo, "expense-claim");
  });
  await test.step("expense-claim-history", async () => {
    await openRoute(
      page,
      PERSONAS.employee,
      "/volunteering/expense-claims",
      "My reimbursement claims",
    );
    await auditMobileLayout(page, testInfo, "expense-claim-history");
  });
  await test.step("expense-claim-workflow", async () => {
    await openRoute(
      page,
      PERSONAS.receipt_reviewer,
      "/volunteering/expense-claim-workflow",
      "Expense claim work",
    );
    await auditMobileLayout(page, testInfo, "expense-claim-workflow");
  });
  await test.step("invoice-generator", async () => {
    await openRoute(
      page,
      PERSONAS.associate,
      "/volunteering/invoice-generator",
      "Prepare an invoice",
    );
    await auditMobileLayout(page, testInfo, "invoice-generator");
    await page.getByRole("button", { name: "Sign on screen" }).click();
    await expect(page.locator("canvas.signature-canvas")).toBeVisible();
    await auditMobileLayout(page, testInfo, "invoice-signature-dialog");
  });
});

test("bank-account and office-address screens", async ({ page }, testInfo) => {
  await test.step("bank-account", async () => {
    await openRoute(
      page,
      PERSONAS.associate,
      "/volunteering/bank-account",
      "Reimbursement bank account",
    );
    await auditMobileLayout(page, testInfo, "bank-account");
  });
  await test.step("office-addresses", async () => {
    await openRoute(
      page,
      PERSONAS.accounts,
      "/volunteering/office-addresses",
      "Office addresses",
    );
    await auditMobileLayout(page, testInfo, "office-addresses");
    await page.getByRole("button", { name: "Add office address" }).click();
    await expect(
      page.getByRole("heading", { name: "Add office address" }),
    ).toBeVisible();
    await auditMobileLayout(page, testInfo, "office-address-form");
  });
});

test("HR and System Management workspaces", async ({ page }, testInfo) => {
  await test.step("hr-management", async () => {
    await openRoute(page, PERSONAS.hr, "/volunteering/home", /^Hello/);
    await expect(
      page.getByRole("heading", { name: "HR Management" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "System Management" }),
    ).toHaveCount(0);
    await openRoute(
      page,
      PERSONAS.hr,
      "/volunteering/hr-management",
      "HR Management",
    );
    await auditMobileLayout(page, testInfo, "hr-management");
    await page.getByRole("button", { name: "Add employee" }).click();
    await expect(
      page.getByRole("heading", { name: "Add employee" }),
    ).toBeVisible();
    await auditMobileLayout(page, testInfo, "hr-employee-form");
  });
  await test.step("system-management", async () => {
    await openRoute(page, PERSONAS.admin, "/volunteering/home", /^Hello/);
    await expect(
      page.getByRole("heading", { name: "HR Management" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "System Management" }),
    ).toBeVisible();
    await openRoute(
      page,
      PERSONAS.admin,
      "/volunteering/system-management",
      "System Management",
    );
    await auditMobileLayout(page, testInfo, "system-management");
    await page.getByRole("button", { name: "Add user" }).click();
    await expect(page.getByRole("heading", { name: "Add user" })).toBeVisible();
    await auditMobileLayout(page, testInfo, "system-user-form");
    await page.getByRole("button", { name: "Back to users" }).click();
    await page
      .locator(".directory-card")
      .filter({ hasText: "Enabled" })
      .first()
      .click();
    await expect(
      page.getByRole("button", { name: "Reset password" }),
    ).toBeVisible();
    await auditMobileLayout(page, testInfo, "system-user-password-reset");

    let resetRequests = 0;
    await page.route(
      "**/api/method/volunteering.volunteering.people_management.send_managed_user_password_reset",
      async (route) => {
        resetRequests += 1;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ message: { user: "local-demo@example.com" } }),
        });
      },
    );
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Reset password" }).click();
    await expect.poll(() => resetRequests).toBe(1);
    await expect(
      page.getByText(/A password reset link was sent to/),
    ).toBeVisible();
  });
});

test("Budget Health, Chart of Accounts and project-account mapping", async ({
  page,
}, testInfo) => {
  await test.step("budget-health", async () => {
    await openRoute(
      page,
      PERSONAS.accounts,
      "/volunteering/budget-health",
      "Budget Health",
    );
    const details = page.locator("main details").first();
    if (await details.count())
      await details.evaluate((element) => (element.open = true));
    await auditMobileLayout(page, testInfo, "budget-health");
  });
  await test.step("project-account-mapping", async () => {
    await openRoute(
      page,
      PERSONAS.accounts,
      "/volunteering/project-account-mapping",
      "Project account mapping",
    );
    const firstProject = page.locator("section.form-card button").first();
    if (await firstProject.count()) {
      await firstProject.click();
      await expect(
        page.getByText(/Approved allocation:/).first(),
      ).toBeVisible();
    }
    await auditMobileLayout(page, testInfo, "project-account-mapping");
  });
  await test.step("chart-of-accounts", async () => {
    await openRoute(
      page,
      PERSONAS.accounts,
      "/volunteering/chart-of-accounts",
      "Chart of Accounts",
    );
    await auditMobileLayout(page, testInfo, "chart-of-accounts");
    await page.getByRole("button", { name: "Add account" }).click();
    await expect(
      page.getByRole("heading", { name: "Add account" }),
    ).toBeVisible();
    await auditMobileLayout(page, testInfo, "chart-of-accounts-form");
  });
});

test("project list, proposal form, approved detail and manager queue", async ({
  page,
}, testInfo) => {
  await test.step("project-list", async () => {
    await openRoute(
      page,
      projectProposer,
      "/volunteering/projects",
      "Projects",
    );
    await auditMobileLayout(page, testInfo, "projects");
    const openProject = page.getByText("Open project →").first();
    if (await openProject.count()) {
      await openProject.click();
      await expect(page).toHaveURL(/project=/);
      await auditMobileLayout(page, testInfo, "project-detail");
    }
  });
  await test.step("project-proposal", async () => {
    await openRoute(
      page,
      projectProposer,
      "/volunteering/projects?new=1",
      "What are we doing?",
    );
    await auditMobileLayout(page, testInfo, "project-proposal");
  });
  await test.step("project-manager-queue", async () => {
    await openRoute(
      page,
      projectManager,
      "/volunteering/project-proposals/review",
      "Review pending proposals",
    );
    await auditMobileLayout(page, testInfo, "project-manager-queue");
  });
});
