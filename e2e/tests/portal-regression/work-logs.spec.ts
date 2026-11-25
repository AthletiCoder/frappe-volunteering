import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

test.beforeEach(({ baseURL }) => {
  if (!baseURL || !["localhost", "127.0.0.1"].includes(new URL(baseURL).hostname)) {
    throw new Error("Work log regression tests must run against an isolated local site.");
  }
});

async function workspace(page: Page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/method/volunteering.volunteering.work_log_portal.get_work_log_calendar", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": (window as any).csrf_token || "" },
      body: "{}",
    });
    if (!response.ok) throw new Error("Could not load work log workspace.");
    return (await response.json()).message;
  });
}

test("Home work logging displays the monthly calendar and blocks future dates", async ({ page }) => {
  await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
  await page.goto("/volunteering/work-logs");
  await expect(page.getByRole("heading", { name: "My work log", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Log work", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Work log calendar" })).toBeVisible();
  const calendar = await workspace(page);
  for (const day of calendar.days) {
    const cell = page.locator(`[data-date="${day.date}"]`);
    if (day.date > calendar.today) await expect(cell).toBeDisabled();
  }
  await expect(page.getByRole("button", { name: "Next month", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Previous month", exact: true }).click();
  await expect(page.getByLabel("Month", { exact: true })).not.toHaveValue(calendar.month);
  await page.getByRole("button", { name: "This month", exact: true }).click();
  await expect(page.getByLabel("Month", { exact: true })).toHaveValue(calendar.month);
  await expect(page.getByRole("button", { name: "Team review", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: calendar.calendar_employee.employee_name, exact: true })).toHaveCount(0);
  const emptyDay = calendar.days.find((day: any) => day.can_open && !day.name);
  expect(emptyDay).toBeTruthy();
  await page.locator(`[data-date="${emptyDay.date}"]`).click();
  await expect(page).toHaveURL(/\/volunteering\/work-logs\?.*new=1/);
  await expect(page.getByRole("link", { name: "Calendar" })).toBeVisible();
});

test("employee draft and submission, manager review, and private notes", async ({ page }) => {
  test.skip(process.env.E2E_WORK_LOG_WRITES !== "1", "Opt-in isolated local work log writes.");
  await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
  await page.goto("/volunteering/work-logs");
  const before = await workspace(page);
  const used = new Set(before.days.filter((row: any) => row.name).map((row: any) => row.date));
  const today = new Date(before.today + "T12:00:00");
  let date = "";
  for (let i = 0; i <= 14; i++) {
    const candidate = new Date(today);
    candidate.setDate(candidate.getDate() - i);
    const value = [candidate.getFullYear(), String(candidate.getMonth() + 1).padStart(2, "0"), String(candidate.getDate()).padStart(2, "0")].join("-");
    if (value >= before.earliest_date && !used.has(value)) { date = value; break; }
  }
  expect(date).not.toBe("");
  await page.goto("/volunteering/work-logs?new=1&date=" + date);
  const title = "Portal work log regression " + Date.now();
  await page.getByLabel("Activity *", { exact: true }).fill(title);
  await expect(page.getByLabel("Output link (optional)", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Add output link/ })).toHaveCount(0);
  await page.getByLabel("Details *", { exact: true }).fill("Prepared lesson materials and reviewed the session attendance. https://example.org/lesson-plan");
  await page.getByLabel("Hours", { exact: true }).selectOption("4");
  const activityHeading = await page.getByRole("heading", { name: "Activity 1", exact: true }).boundingBox();
  const timePicker = await page.locator(".worklog-time-picker").first().boundingBox();
  expect(activityHeading).not.toBeNull(); expect(timePicker).not.toBeNull();
  expect(activityHeading!.x + activityHeading!.width).toBeLessThanOrEqual(timePicker!.x + 2);
  expect(Math.abs(activityHeading!.y - timePicker!.y)).toBeLessThan(20);
  await expect(page.getByRole("heading", { name: before.calendar_employee.employee_name, exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "+ Add activity", exact: true }).click();
  await page.getByLabel("Activity *", { exact: true }).nth(1).fill("Coordinate volunteers");
  await page.getByLabel("Details *", { exact: true }).nth(1).fill("Confirmed the volunteer assignments for the next project visit.");
  await page.getByLabel("Hours", { exact: true }).nth(1).selectOption("2");
  await page.getByLabel("Minutes", { exact: true }).nth(1).selectOption("30");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Draft saved");
  await page.reload();
  await expect(page.getByLabel("Activity *", { exact: true }).first()).toHaveValue(title);
  await expect(page.getByLabel("Details *", { exact: true }).first()).toHaveValue("Prepared lesson materials and reviewed the session attendance. https://example.org/lesson-plan");
  await expect(page.getByLabel("Hours", { exact: true }).nth(1)).toHaveValue("2");
  await expect(page.getByLabel("Minutes", { exact: true }).nth(1)).toHaveValue("30");
  page.once("dialog", async dialog => { await dialog.accept(); });
  await page.getByRole("button", { name: "Submit log", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Work log submitted");
  await expect(page.locator(".status").filter({ hasText: "Submitted" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save draft", exact: true })).toHaveCount(0);
  await expect(page.getByText("2 activities · 6 h 30 min", { exact: true })).toBeVisible();

  await page.context().clearCookies();
  await loginViaAPI(page.request, PERSONAS.manager.email, PERSONAS.manager.password);
  await page.goto("/volunteering/work-logs?view=team");
  await page.locator(".person-card").filter({ hasText: before.calendar_employee.employee_name }).click();
  await page.locator(`[data-date="${date}"]`).click();
  await expect(page.getByRole("heading", { name: "Manager review", exact: true })).toBeVisible();
  await page.getByLabel("Private review notes", { exact: true }).fill("Private manager-only regression note.");
  await page.getByRole("button", { name: "Mark as reviewed", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Work log reviewed");
  await expect(page.locator(".status").filter({ hasText: "Reviewed" })).toBeVisible();

  await page.context().clearCookies();
  await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
  await page.goto("/volunteering/work-logs");
  await page.locator(`[data-date="${date}"]`).click();
  await expect(page.locator(".status").filter({ hasText: "Reviewed" })).toBeVisible();
  await expect(page.getByText("Private manager-only regression note.")).toHaveCount(0);
});


test("reviewer sees people first and calendar navigation stays scoped to the selected employee", async ({ page }) => {
  await loginViaAPI(page.request, PERSONAS.manager.email, PERSONAS.manager.password);
  await page.goto("/volunteering/work-logs");
  await expect(page.getByRole("navigation", { name: "Work log views" })).toBeVisible();
  await page.getByRole("button", { name: "Team review", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Team work log", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your team", exact: true })).toBeVisible();
  const reviewTab = page.getByRole("button", { name: "Team review", exact: true });
  const box = await reviewTab.boundingBox();
  expect(box).not.toBeNull();
  expect(await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.closest('button')?.textContent?.trim(), { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 })).toBe("Team review");
  const person = page.locator(".person-card").first();
  await expect(person).toBeVisible();
  await person.click();
  const selected = new URL(page.url()).searchParams.get("employee");
  expect(selected).toBeTruthy();
  await expect(page.getByRole("region", { name: "Work log calendar" })).toBeVisible();
  await page.getByRole("button", { name: "Previous month", exact: true }).click();
  await expect(page.getByRole("region", { name: "Work log calendar" })).toBeVisible();
  expect(new URL(page.url()).searchParams.get("employee")).toBe(selected);
  await page.getByRole("button", { name: "Back to team", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Team work log", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your team", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "My logs", exact: true }).click();
  await expect(page.getByRole("region", { name: "Work log calendar" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "My work log", exact: true })).toBeVisible();
  expect(new URL(page.url()).searchParams.has("employee")).toBe(false);
});
