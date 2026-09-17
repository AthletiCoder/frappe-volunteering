import { expect, test } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { getList } from "../../helpers/frappe";
import { PERSONAS } from "../../helpers/personas";

test.describe("Project single-page layout @projects @ui", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(
      page.request,
      PERSONAS.admin.email,
      PERSONAS.admin.password,
    );
  });

  test("saved Project displays all former tabs in one ordered page @regression", async ({
    page,
  }) => {
    const projects = await getList<{ name: string }>(page.request, "Project", {
      fields: ["name"],
      limit: 1,
    });
    expect(projects.length).toBeGreaterThan(0);
    await page.goto(`/desk/project/${encodeURIComponent(projects[0].name)}`);

    const layout = page.locator(
      ".form-layout.volunteering-project-single-page",
    );
    await expect(layout).toBeVisible();
    await expect(layout.locator(".form-tabs-list")).toBeHidden();
    await expect(layout.locator(".volunteering-project-tab-title")).toHaveText([
      "Details",
      "Costing",
      "Progress",
      "More Info",
      "Connections",
    ]);

    let previousY = -1;
    for (const fieldname of [
      "__details",
      "costing_tab",
      "monitor_progress_tab",
      "more_info_tab",
      "connections_tab",
    ]) {
      const pane = layout.locator(`#project-${fieldname}`);
      await expect(pane).toBeVisible();
      const box = await pane.boundingBox();
      expect(box!.y).toBeGreaterThan(previousY);
      previousY = box!.y;
    }

    for (const fieldname of [
      "project_name",
      "expected_start_date",
      "cost_center",
      "collect_progress",
    ]) {
      await expect(
        layout
          .locator(`.frappe-control[data-fieldname="${fieldname}"]`)
          .first(),
      ).toBeVisible();
    }

    await page.evaluate(async () => {
      const frm = (window as any).cur_frm;
      frm.layout.sections
        .find((section: any) => section.df.fieldname === "section_break_18")
        .collapse(true);
      await frm.refresh();
    });
    await expect(layout.locator(".volunteering-project-tab-title")).toHaveCount(
      5,
    );
    await expect(
      layout.locator('[data-fieldname="section_break_18"] > .section-body'),
    ).toBeVisible();
    await expect(layout.locator(".form-tabs-list")).toBeHidden();
  });

  test("new Project also uses the single-page layout without saving @regression", async ({
    page,
  }) => {
    await page.goto("/desk/project/new");
    const layout = page.locator(
      ".form-layout.volunteering-project-single-page",
    );
    await expect(layout).toBeVisible();
    await expect(layout.locator(".form-tabs-list")).toBeHidden();
    await expect(
      layout.locator('.frappe-control[data-fieldname="project_name"]'),
    ).toBeVisible();
    await expect(
      layout.locator('.frappe-control[data-fieldname="cost_center"]'),
    ).toBeVisible();
    await expect(
      layout.locator('.frappe-control[data-fieldname="collect_progress"]'),
    ).toBeVisible();
  });
});
