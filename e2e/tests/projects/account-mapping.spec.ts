import { expect, test } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

test("Accounts Manager opens the approved project-label mapping interface", async ({
  page,
}) => {
  await loginViaAPI(
    page.request,
    PERSONAS.accounts.email,
    PERSONAS.accounts.password,
  );
  await page.goto("/volunteering/project-account-mapping");
  await expect(
    page.getByRole("heading", { name: "Project account mapping" }),
  ).toBeVisible();
  await expect(
    page.getByText("Approved projects", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  const project = page.locator("section.form-card button").first();
  await expect(project).toBeVisible();
  const projectId = await project.getAttribute("data-project-name");
  expect(projectId).toBeTruthy();
  await project.click();
  await expect(page).toHaveURL(new RegExp(`project=${projectId}`));
  await expect(
    page.getByText("Approved projects", { exact: true }),
  ).toHaveCount(0);
  const mappingForm = page.locator("form.form-card");
  await expect(mappingForm).toBeVisible();
  await expect(mappingForm).toBeInViewport();
  await expect(page.getByText(/Approved allocation:/).first()).toBeVisible();
  await expect(page.getByText(/A label may suggest several ledger accounts/)).toBeVisible();
  if (!(await page.getByRole("combobox", { name: /Suggested account/ }).count())) {
    await page.getByRole("button", { name: "+ Suggest an account" }).first().click();
  }
  await expect(
    page.getByRole("combobox", { name: /Suggested account/ }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Choose another project" }).click();
  await expect(
    page.getByText("Approved projects", { exact: true }),
  ).toBeVisible();
  await expect(page).not.toHaveURL(/project=/);

  await page.goto(
    `/volunteering/project-account-mapping?project=${encodeURIComponent(projectId)}`,
  );
  await expect(page.locator("form.form-card")).toBeVisible();
  await expect(page.getByText(/Approved allocation:/).first()).toBeVisible();
});

test("non-Accounts Manager cannot access project account mapping", async ({
  page,
}) => {
  await loginViaAPI(
    page.request,
    PERSONAS.employee.email,
    PERSONAS.employee.password,
  );
  await page.goto("/volunteering/project-account-mapping");
  await expect(page.getByRole("alert")).toContainText(/Only Accounts Managers/);
  await expect(
    page.getByText("Approved projects", { exact: true }),
  ).toHaveCount(0);
});
