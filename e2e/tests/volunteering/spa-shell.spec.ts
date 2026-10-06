import { expect, test, type Page } from "@playwright/test";
import { callMethod } from "../../helpers/frappe";
import { HomePage } from "../../pages/home.page";
import { personaStorage } from "../../helpers/personas";

async function openMenu(page: Page, containing: string) {
  const menu = page.locator('nav[aria-label="Sections"] details').filter({ hasText: containing }).first();
  await menu.locator("summary").click();
  return menu;
}

test.describe("SPA shell @smoke @volunteering", () => {
  test.describe("as employee", () => {
    test.use({ storageState: personaStorage("employee") });

    test("previous requests remain available in the side menu", async ({ page }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.locator('a[href="/desk/leave-application"]')).toHaveCount(1);
      await expect(nav.locator('a[href="/volunteering/expense-claims"]')).toHaveCount(1);
      await expect(nav.locator('a[href="/desk/daily-work-log"]')).toHaveCount(1);
    });

    test("visible Home shortcuts retain meaningful icons and colour grades", async ({ page }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      for (const [actionId, icon, tone] of [
        ["log_work", "clock", "blue"],
        ["leave", "calendar-away", "violet"],
      ]) {
        const tile = page.locator(`[data-action-id="${actionId}"]`);
        await expect(tile).toBeVisible();
        await expect(tile.locator("[data-icon-name]")).toHaveAttribute("data-icon-name", icon);
        await expect(tile.locator("[data-icon-tone]")).toHaveAttribute("data-icon-tone", tone);
      }
    });

    test("Previous leave count matches get_home_payload", async ({ page, request }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      const payload = await callMethod<{ actions: { time: { id: string; pending?: number }[] } }>(
        request, "volunteering.volunteering.home_service.get_home_payload", {}, "employee",
      );
      const leave = payload.actions.time.find((row) => row.id === "leave");
      const pill = page.locator('nav[aria-label="Sections"] a[href="/desk/leave-application"]');
      await expect(pill).toContainText(String(leave?.pending ?? 0));
    });

    test("side menu opens Advances while Home shows Waiting on you", async ({ page }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.getByRole("link", { name: "Home" })).toBeVisible();
      await expect(page.getByRole("heading", { name: /Waiting on you/i })).toBeVisible();
      const menu = await openMenu(page, "Advances");
      await menu.locator('a[href="/volunteering/advances"]').click();
      await expect(page).toHaveURL(/\/volunteering\/advances/);
      await expect(page.getByRole("heading", { name: "Advances", level: 1 })).toBeVisible();
    });

    test("Home search finds permitted actions", async ({ page }) => {
      await page.goto("/volunteering/home");
      await page.getByRole("button", { name: "Search pages and actions" }).click();
      const search = page.getByRole("dialog", { name: "Search pages and actions" });
      await search.getByRole("searchbox", { name: "Search your pages and actions" }).fill("invoice");
      await expect(search.getByRole("link", { name: /Prepare an invoice/i })).toBeVisible();
      await expect(search.getByRole("link", { name: /System management/i })).toHaveCount(0);
    });

    test("invoice preparation lives on each active project rather than Quick actions", async ({ page }) => {
      await page.goto("/volunteering/home");
      const project = page.locator("main section[aria-labelledby='member-projects-title'] article").first();
      await expect(project.getByRole("link", { name: "Prepare an invoice" }))
        .toHaveAttribute("href", "/volunteering/invoice-generator");
      await expect(page.getByRole("region", { name: "Quick actions" })).toHaveCount(0);
      await expect(page.getByRole("link", { name: "Open all projects" }))
        .toHaveAttribute("href", "/volunteering/projects?view=approved");
    });

    test("mobile Home keeps role navigation in the More menu", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/volunteering/home");
      await expect(page.getByRole("navigation", { name: "Mobile" })).toBeVisible();
      await page.getByRole("button", { name: "More sections" }).click();
      const menu = page.getByRole("complementary", { name: "Mobile menu" });
      await expect(menu.locator("summary").filter({ hasText: "Projects" })).toBeVisible();
      await expect(menu.getByText("System management", { exact: true })).toHaveCount(0);
    });

    test("/todos opens Waiting workbench", async ({ page }) => {
      await page.goto("/volunteering/todos");
      await expect(page).toHaveURL(/\/volunteering\/todos/);
      await expect(page.getByRole("heading", { name: "Waiting", level: 1 })).toBeVisible();
      await expect(page.getByRole("button", { name: /All/i })).toBeVisible();
    });

    test("theme switch is hidden and stored dark preferences are reset", async ({ page }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      await expect(page.getByRole("button", { name: "Toggle colour theme" })).toHaveCount(0);
      await page.evaluate(() => localStorage.setItem("volunteering.theme", "dark"));
      await page.reload();
      await expect(page.locator("html")).not.toHaveClass(/dark/);
      await expect.poll(() => page.evaluate(() => localStorage.getItem("volunteering.theme"))).toBe("light");
    });
  });

  test.describe("as accounts", () => {
    test.use({ storageState: personaStorage("accounts") });

    test("side menu includes Budget Health", async ({ page }) => {
      await page.goto("/volunteering/home");
      const menu = await openMenu(page, "Budget health");
      await menu.locator('a[href="/volunteering/budget-health"]').click();
      await expect(page).toHaveURL(/\/volunteering\/budget-health/);
      await expect(page.getByRole("heading", { name: "Budget Health", level: 1 })).toBeVisible();
    });

    test("Home prioritises Accounts responsibilities and keeps bank review in the menu", async ({ page }) => {
      await page.goto("/volunteering/home");
      await expect(page.getByRole("heading", { name: "Your shortcuts" })).toBeVisible();
      await expect(page.locator('[data-action-id="classify_claims"]')).toBeVisible();
      await expect(page.locator('[data-action-id="donations"]')).toBeVisible();
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.locator('a[href="/volunteering/bank-account?queue=1"]')).toHaveCount(1);
    });
  });

  test.describe("as HR", () => {
    test.use({ storageState: personaStorage("hr") });
    test("Home highlights HR management", async ({ page }) => {
      await page.goto("/volunteering/home");
      await expect(page.getByRole("heading", { name: "Your shortcuts" })).toBeVisible();
      await expect(page.locator('[data-action-id="manage_employees"]')).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Sections" }).locator("summary").filter({ hasText: "HR management" })).toBeVisible();
    });
  });

  test.describe("as administrator", () => {
    test.use({ storageState: personaStorage("admin") });
    test("Home exposes both management areas", async ({ page }) => {
      await page.goto("/volunteering/home");
      await expect(page.locator('[data-action-id="manage_users"]')).toBeVisible();
      await expect(page.locator('[data-action-id="manage_employees"]')).toBeVisible();
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.locator("summary").filter({ hasText: "System management" })).toBeVisible();
      await expect(nav.locator("summary").filter({ hasText: "HR management" })).toBeVisible();
    });
  });

  test.describe("as coordinator", () => {
    test.use({ storageState: personaStorage("coordinator") });
    test("side menu includes the Volunteering workspace", async ({ page }) => {
      await page.goto("/volunteering/home");
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.getByRole("link", { name: "Home" })).toBeVisible();
      const menu = await openMenu(page, "Campaign dashboard");
      await expect(menu.locator('a[href="/desk/volunteering"]')).toHaveCount(1);
    });
  });

  for (const persona of ["employee", "manager", "accounts", "hr", "admin", "coordinator"] as const) {
    test.describe(`Home compatibility as ${persona}`, () => {
      test.use({ storageState: personaStorage(persona) });
      test("retains every role-provided action and supporting area", async ({ page, request }) => {
        await page.goto("/volunteering/home");
        await expect(page.locator("main h1")).toHaveText(/^(Home|Your active projects)$/);
        const payload = await callMethod<{
          actions: Record<string, { route: string; list_route?: string }[]>;
          resume: unknown[];
          people: { route: string }[];
          admin: { route: string }[];
          programs?: { workspace_route: string; report_route: string };
        }>(request, "volunteering.volunteering.home_service.get_home_payload", {}, persona);
        const navRoutes = await page.getByRole("navigation", { name: "Sections" }).locator("a[href]").evaluateAll(
          (links) => links.map((link) => (link as HTMLAnchorElement).getAttribute("href")),
        );
        const expected = [
          ...Object.values(payload.actions).flatMap((actions) => actions.flatMap((action) => [action.route, action.list_route].filter(Boolean))),
          ...payload.people.map((link) => link.route),
          ...payload.admin.map((link) => link.route),
          ...(payload.programs ? [payload.programs.workspace_route, payload.programs.report_route] : []),
        ];
        for (const route of expected) expect(navRoutes, `${persona} lost ${route}`).toContain(route);
        if (payload.resume.length) await expect(page.getByRole("heading", { name: "Resume drafts" })).toBeVisible();
      });
    });
  }
});
