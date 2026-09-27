import { expect, test } from "@playwright/test";
import { callMethod } from "../../helpers/frappe";
import { HomePage } from "../../pages/home.page";
import { personaStorage } from "../../helpers/personas";

test.describe("SPA shell @smoke @volunteering", () => {
  test.describe("as employee", () => {
    test.use({ storageState: personaStorage("employee") });

    test("Home previous-request pills sit on new-request cards", async ({
      page,
    }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      await expect(
        page.getByRole("link", { name: "Previous leave" }),
      ).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Previous claims" }),
      ).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Previous work logs" }),
      ).toBeVisible();
    });

    test("Home tiles use meaningful icons and semantic colour grades", async ({
      page,
    }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();

      const expectedVisuals = {
        approved_projects: ["folder-check", "green"],
        office_addresses: ["map-pin", "cyan"],
        log_work: ["clock", "blue"],
        wfh: ["home", "green"],
        leave: ["calendar-away", "violet"],
        fix_attendance: ["calendar-check", "amber"],
        advance: ["coins", "blue"],
        claim: ["receipt", "amber"],
        invoice_generator: ["invoice", "cyan"],
        invoice_expense_claim: ["invoice-claim", "green"],
      };

      for (const [actionId, [icon, tone]] of Object.entries(expectedVisuals)) {
        const tile = page.locator(`[data-action-id="${actionId}"]`);
        await expect(tile).toBeVisible();
        await expect(tile.locator("[data-icon-name]")).toHaveAttribute(
          "data-icon-name",
          icon,
        );
        await expect(tile.locator("[data-icon-tone]")).toHaveAttribute(
          "data-icon-tone",
          tone,
        );
      }
    });

    test("Previous leave pill count matches get_home_payload", async ({
      page,
      request,
    }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      const payload = await callMethod<{
        actions: { time: { id: string; pending?: number }[] };
      }>(
        request,
        "volunteering.volunteering.home_service.get_home_payload",
        {},
        "employee",
      );
      const leave = payload.actions.time.find((row) => row.id === "leave");
      const pill = page.getByRole("link", { name: "Previous leave" });
      await expect(pill).toHaveAttribute("href", "/desk/leave-application");
      await expect(pill).toContainText(String(leave?.pending ?? 0));
    });

    test("header nav opens Advances and shows Waiting on Home", async ({
      page,
    }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.getByRole("link", { name: "Home" })).toBeVisible();
      await expect(nav.getByRole("link", { name: "To-do" })).toHaveCount(0);
      await expect(nav.getByRole("link", { name: "Advances" })).toBeVisible();
      await expect(nav.getByRole("link", { name: "Volunteering" })).toHaveCount(
        0,
      );
      await expect(nav.getByRole("link", { name: "Budgets" })).toHaveCount(0);
      await expect(
        page.getByRole("heading", {
          name: /Waiting on you|You’re clear|You're clear/i,
          level: 2,
        }),
      ).toBeVisible();
      await nav.getByRole("link", { name: "Advances" }).click();
      await expect(page).toHaveURL(/\/volunteering\/advances/);
      await expect(
        page.getByRole("heading", { name: "Advances", level: 1 }),
      ).toBeVisible();
    });

    test("Home search finds permitted actions", async ({ page }) => {
      await page.goto("/volunteering/home");
      await page.getByRole("button", { name: "Search pages and actions" }).click();
      const search = page.getByRole("dialog", { name: "Search pages and actions" });
      await search.getByRole("searchbox", { name: "Search your pages and actions" }).fill("invoice");
      await expect(search.getByRole("link", { name: /Prepare an invoice/i })).toBeVisible();
      await expect(search.getByRole("link", { name: /System management/i })).toHaveCount(0);
    });

    test("Quick actions include invoice preparation, not approved projects", async ({ page }) => {
      await page.goto("/volunteering/home");
      const quick = page.getByRole("region", { name: "Quick actions" });
      await expect(quick.getByRole("link", { name: "Prepare an invoice" }))
        .toHaveAttribute("href", "/volunteering/invoice-generator");
      await expect(quick.getByRole("link", { name: "Approved projects" })).toHaveCount(0);
      await expect(page.locator('[data-action-id="approved_projects"]')).toBeVisible();
    });

    test("mobile Home keeps role navigation in the More menu", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/volunteering/home");
      await expect(page.getByRole("navigation", { name: "Mobile" })).toBeVisible();
      await page.getByRole("button", { name: "More sections" }).click();
      const menu = page.getByRole("complementary", { name: "Mobile menu" });
      await expect(menu.getByRole("link", { name: "Projects" })).toBeVisible();
      await expect(menu.getByRole("link", { name: "System management" })).toHaveCount(0);
    });

    test("/todos opens Waiting workbench", async ({ page }) => {
      await page.goto("/volunteering/todos");
      await expect(page).toHaveURL(/\/volunteering\/todos/);
      await expect(
        page.getByRole("heading", { name: "Waiting", level: 1 }),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: /All/i })).toBeVisible();
    });

    test("theme switch is hidden and stored dark preferences are reset", async ({
      page,
    }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      await expect(
        page.getByRole("button", { name: "Toggle colour theme" }),
      ).toHaveCount(0);
      await page.evaluate(() =>
        localStorage.setItem("volunteering.theme", "dark"),
      );
      await page.reload();
      await expect(page.locator("html")).not.toHaveClass(/dark/);
      await expect
        .poll(() =>
          page.evaluate(() => localStorage.getItem("volunteering.theme")),
        )
        .toBe("light");
    });
  });

  test.describe("as accounts", () => {
    test.use({ storageState: personaStorage("accounts") });

    test("header nav includes Budgets", async ({ page }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      await page
        .getByRole("navigation", { name: "Sections" })
        .getByRole("link", { name: "Budgets" })
        .click();
      await expect(page).toHaveURL(/\/volunteering\/budget-health/);
      await expect(
        page.getByRole("heading", { name: "Budget Health", level: 1 }),
      ).toBeVisible();
    });

    test("Home prioritises accounts work", async ({ page }) => {
      await page.goto("/volunteering/home");
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.getByRole("link", { name: "Accounts work" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Accounts", exact: true })).toBeVisible();
      await expect(page.getByRole("region", { name: "Quick actions" }).getByRole("link", { name: "Review reimbursement bank accounts" }))
        .toHaveAttribute("href", "/volunteering/bank-account?queue=1");
    });
  });

  test.describe("as HR", () => {
    test.use({ storageState: personaStorage("hr") });
    test("Home places HR management first", async ({ page }) => {
      await page.goto("/volunteering/home");
      await expect(page.getByRole("heading", { name: "HR management" })).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "HR management" })).toBeVisible();
    });
  });

  test.describe("as administrator", () => {
    test.use({ storageState: personaStorage("admin") });
    test("Home exposes both management areas", async ({ page }) => {
      await page.goto("/volunteering/home");
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.getByRole("link", { name: "System management" })).toBeVisible();
      await expect(nav.getByRole("link", { name: "HR management" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Quick actions" })).toBeVisible();
    });
  });

  test.describe("as coordinator", () => {
    test.use({ storageState: personaStorage("coordinator") });

    test("header nav includes Volunteering next to Home and Advances", async ({
      page,
    }) => {
      const home = new HomePage(page);
      await home.goto();
      await home.expectLoaded();
      const nav = page.getByRole("navigation", { name: "Sections" });
      await expect(nav.getByRole("link", { name: "Home" })).toBeVisible();
      await expect(nav.getByRole("link", { name: "Advances" })).toBeVisible();
      const volunteering = nav.getByRole("link", { name: "Volunteering" });
      await expect(volunteering).toBeVisible();
      await expect(volunteering).toHaveAttribute("href", "/desk/volunteering");
    });
  });

  for (const persona of ["employee", "manager", "accounts", "hr", "admin", "coordinator"] as const) {
    test.describe(`Home compatibility as ${persona}`, () => {
      test.use({ storageState: personaStorage(persona) });
      test("retains every role-provided action and supporting area", async ({ page, request }) => {
        await page.goto("/volunteering/home");
        await page.getByRole("heading", { name: /^Hello /, level: 1 }).waitFor();
        const payload = await callMethod<{
          actions: Record<string, { id: string; route: string; list_route?: string }[]>;
          nav: Record<string, boolean>;
          resume: unknown[];
          people: unknown[];
          admin: unknown[];
          programs: unknown;
        }>(request, "volunteering.volunteering.home_service.get_home_payload", {}, persona);
        const quick = page.getByRole("region", { name: "Quick actions" });
        await expect(quick.getByRole("link", { name: "Approved projects" })).toHaveCount(0);
        if (Object.values(payload.actions).flat().some((action) => action.id === "invoice_generator")) {
          await expect(quick.getByRole("link", { name: "Prepare an invoice" })).toBeVisible();
        }
        const nav = page.getByRole("navigation", { name: "Sections" });
        if (payload.nav.projects) await expect(nav.getByRole("link", { name: "Projects" })).toBeVisible();
        if (payload.nav.advances) await expect(nav.getByRole("link", { name: "Advances" })).toBeVisible();
        if (payload.nav.team) await expect(nav.getByRole("link", { name: "My team" })).toBeVisible();
        if (payload.nav.volunteering) await expect(nav.getByRole("link", { name: "Volunteering" })).toBeVisible();
        if (payload.nav.budget_health) await expect(nav.getByRole("link", { name: "Budgets" })).toBeVisible();
        const rendered = await page.locator("[data-action-id]").evaluateAll((nodes) =>
          nodes.map((node) => node.getAttribute("data-action-id")),
        );
        for (const action of Object.values(payload.actions).flat()) {
          expect(rendered, `${persona} lost Home action ${action.id}`).toContain(action.id);
          await expect(page.locator(`[data-action-id="${action.id}"] a[href="${action.route}"]`).first())
            .toBeVisible();
          if (action.list_route) {
            await expect(page.locator(`[data-action-id="${action.id}"] a[href="${action.list_route}"]`).first())
              .toBeVisible();
          }
        }
        if (payload.resume.length) await expect(page.getByRole("heading", { name: "Resume drafts" })).toBeVisible();
        if (payload.programs || payload.people.length || payload.admin.length) {
          await expect(page.getByText("More resources", { exact: false })).toBeVisible();
        }
      });
    });
  }
});
