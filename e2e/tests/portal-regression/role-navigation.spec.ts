import { expect, test } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

const actors = [
  { name: "employee", email: PERSONAS.employee.email, password: PERSONAS.employee.password },
  { name: "projects manager", email: "demo.project.manager@sevamrita.local", password: process.env.E2E_PROJECT_PASSWORD || PERSONAS.employee.password },
  { name: "accounts manager", email: PERSONAS.accounts.email, password: PERSONAS.accounts.password },
  { name: "HR manager", email: PERSONAS.hr.email, password: PERSONAS.hr.password },
  { name: "administrator", email: PERSONAS.admin.email, password: PERSONAS.admin.password },
];

test.beforeEach(({ baseURL }) => {
  if (!baseURL || !["127.0.0.1", "localhost", "sevamrita.local"].includes(new URL(baseURL).hostname)) {
    throw new Error("Portal regression must run against the local demo site only.");
  }
});

for (const actor of actors) {
  test(`${actor.name} can find every permitted action in the sidebar`, async ({ page }) => {
    await loginViaAPI(page.request, actor.email, actor.password);
    await page.goto("/volunteering/home");
    await expect(page.locator("main").getByRole("heading", { name: /^(Home|Your active projects)$/ })).toBeVisible();
    const payload = await page.evaluate(async () => {
      const response = await fetch("/api/method/volunteering.volunteering.home_service.get_home_payload", { credentials: "same-origin" });
      if (!response.ok) throw new Error(`Home payload failed: ${response.status}`);
      return (await response.json()).message;
    });
    const routes = Object.values(payload.actions || {}).flatMap((actions: any) =>
      (actions || []).flatMap((action: any) => [action.route, action.list_route].filter(Boolean)),
    );
    const sidebarRoutes = await page.getByRole("navigation", { name: "Sections" }).locator("a[href]").evaluateAll(
      (anchors) => anchors.map((anchor) => new URL((anchor as HTMLAnchorElement).href).pathname + new URL((anchor as HTMLAnchorElement).href).search),
    );
    for (const route of routes) {
      expect(sidebarRoutes, `${actor.name} is missing ${route} from the sidebar`).toContain(route);
    }
    await expect(page.getByRole("link", { name: "Profile", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Logout", exact: true })).toBeVisible();
  });
}

test("employee Home retains active-project actions as the first content section", async ({ page }) => {
  await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
  await page.goto("/volunteering/home");
  await expect(page.locator("main h1")).toHaveText("Your active projects");
  const project = page.locator("main section[aria-labelledby='member-projects-title'] article").first();
  await expect(project).toBeVisible();
  await expect(project.getByRole("link", { name: "Submit an expense" })).toBeVisible();
  await expect(project.getByRole("link", { name: "Request an advance" })).toBeVisible();
  await expect(project.getByRole("link", { name: "Prepare an invoice" })).toBeVisible();
  await expect(project.getByRole("link", { name: "View project" })).toBeVisible();
  await expect(page.getByText("Everything you can do")).toHaveCount(0);
});
