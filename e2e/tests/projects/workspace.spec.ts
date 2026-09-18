import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

const workspaceService = "volunteering.volunteering.project_workspace.";
const proposalService = "volunteering.volunteering.project_proposals.";
const proposer = "demo.project.user@sevamrita.local";
const manager = "demo.project.manager@sevamrita.local";
const viewer = "demo.project.viewer@sevamrita.local";
const password = process.env.E2E_PROJECT_PASSWORD || PERSONAS.employee.password;
let proposalId = "";
let projectId = "";
let financialDocumentUrl = "";
const projectName = `_Demo governed project ${Date.now()}`;

async function signIn(page: Page, email: string) {
  await page.context().clearCookies();
  await loginViaAPI(page.request, email, password);
  await page.goto("/volunteering/projects");
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
}

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
      return { status: response.status, data: await response.json() };
    },
    { method, args },
  );
}

test.describe.serial("Governed project workspace @projects @ui", () => {
  test.skip(
    process.env.E2E_PROJECT_DEMOS !== "1",
    "Opt-in suite: requires the local project/account demo personas.",
  );

  test.beforeAll(async ({ baseURL }) => {
    if (
      !baseURL ||
      !["127.0.0.1", "localhost", "sevamrita.local"].includes(
        new URL(baseURL).hostname,
      )
    ) {
      throw new Error(
        "Project demo browser tests may only write to localhost.",
      );
    }
  });

  test("proposer saves evidence and submits without creating an effective project", async ({
    page,
  }) => {
    await signIn(page, proposer);
    await page.getByRole("button", { name: "Propose a project" }).click();
    await expect(
      page.getByRole("heading", { name: "What are we doing?" }),
    ).toBeVisible();

    const options = (await api(page, workspaceService + "get_setup_options"))
      .data.message;
    const centre = options.cost_centres[0].name;
    await expect(page.getByLabel(/^Company/)).toHaveCount(0);
    await page.getByLabel("Project name *", { exact: true }).fill(projectName);
    await page
      .getByLabel("Purpose / scope *", { exact: true })
      .fill("Run a governed local programme with reviewed scope and budgets.");
    await page.getByLabel(/^Operational status \*/).selectOption("Active");
    await page.getByLabel("Find participants").fill(PERSONAS.employee.email);
    await page
      .getByLabel(`Add participant ${PERSONAS.employee.email}`, { exact: true })
      .check();
    await page.getByLabel(/^Default cost centre/).selectOption(centre);
    await page
      .getByLabel(/^Overall project budget control/)
      .selectOption("Strict");
    await page.getByLabel(/^Total approved budget/).fill("10000");
    await page
      .getByLabel(/^Expense-category budget control/)
      .selectOption("Warn Only");
    await page
      .getByLabel("Employee-facing label *", { exact: true })
      .fill("Programme materials");
    await page.getByLabel(/^Budget allocation/).fill("8000");
    await page
      .getByRole("button", { name: "Save draft / edits" })
      .last()
      .click();
    await expect(page).toHaveURL(/proposal=/);
    proposalId = new URL(page.url()).searchParams.get("proposal")!;
    await expect(
      page.getByRole("status").filter({ hasText: "Request saved" }),
    ).toBeVisible();

    await page.getByLabel("Document visibility").selectOption("Basic");
    await page.getByLabel("Add a supporting document").setInputFiles({
      name: "local-project-plan.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Local project plan; test data only."),
    });
    await expect(
      page.getByRole("link", { name: /local-project-plan/ }),
    ).toBeVisible();
    await page.getByLabel("Document visibility").selectOption("Financial");
    await page.getByLabel("Add a supporting document").setInputFiles({
      name: "local-approved-budget.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Local approved budget; test data only."),
    });
    await expect(
      page.getByRole("link", { name: /local-approved-budget/ }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Submit for project approval" })
      .click();
    await expect(
      page.getByText("New Project · Pending Approval"),
    ).toBeVisible();
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: "Submitted for project approval" }),
    ).toBeVisible();

    const approvedProjects = (
      await api(page, workspaceService + "get_projects")
    ).data.message.projects;
    expect(approvedProjects.map((row: any) => row.project_name)).not.toContain(
      projectName,
    );
  });

  test("one manager edits and approves the proposal", async ({ page }) => {
    await signIn(page, manager);
    await page.goto(`/volunteering/projects?proposal=${proposalId}`);
    await expect(
      page.getByText("New Project · Pending Approval"),
    ).toBeVisible();
    await page
      .getByLabel("Purpose / scope *", { exact: true })
      .fill("Manager-reviewed governed programme scope.");
    await page
      .getByLabel("Review comments")
      .fill("Scope and budget checked for the local demonstration.");
    await page.getByRole("button", { name: "Approve with my edits" }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Approved" }),
    ).toBeVisible();
    await expect(page.getByText("New Project · Approved")).toBeVisible();
    const approved = (
      await api(page, proposalService + "get_proposal", {
        proposal: proposalId,
      })
    ).data.message;
    projectId = approved.project;
    expect(projectId).toMatch(/^PROJ-/);

    await page.getByRole("link", { name: "Open approved project" }).click();
    await expect(page).toHaveURL(new RegExp(`project=${projectId}`));
    await expect(
      page.getByLabel("Purpose / scope *", { exact: true }),
    ).toHaveValue("Manager-reviewed governed programme scope.");
    await expect(
      page.getByLabel("Purpose / scope *", { exact: true }),
    ).toBeDisabled();
    const project = (
      await api(page, workspaceService + "get_project", {
        project: projectId,
      })
    ).data.message;
    expect(project.total_approved_budget).toBe(10000);
    expect(project.revisions).toHaveLength(1);
    financialDocumentUrl = project.attachments.find((row: any) =>
      row.file_name.startsWith("local-approved-budget"),
    ).file_url;
  });

  test("basic member can claim but sees neither financial values nor financial evidence", async ({
    page,
  }) => {
    await signIn(page, PERSONAS.employee.email);
    await page.goto(`/volunteering/projects?project=${projectId}`);
    await expect(
      page.getByRole("heading", { name: "Expense categories for your bills" }),
    ).toBeVisible();
    await expect(page.getByText(/^Programme materials/)).toBeVisible();
    await expect(page.getByLabel(/^Total approved budget/)).toHaveCount(0);
    await expect(page.getByText(/local-project-plan/)).toBeVisible();
    await expect(page.getByText(/local-approved-budget/)).toHaveCount(0);
    expect((await page.request.get(financialDocumentUrl)).ok()).toBeFalsy();

    const project = (
      await api(page, workspaceService + "get_project", {
        project: projectId,
      })
    ).data.message;
    expect(project.total_approved_budget).toBeUndefined();
    expect(project.account_budgets).toBeUndefined();
    expect(project.permitted_accounts).toHaveLength(1);
  });

  test("company viewer sees every approved project read-only without financials", async ({
    page,
  }) => {
    await signIn(page, viewer);
    await expect(page.getByText(projectName)).toBeVisible();
    await page.getByRole("button").filter({ hasText: projectName }).click();
    await expect(
      page.getByLabel("Purpose / scope *", { exact: true }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Propose changes" }),
    ).toHaveCount(0);
    await expect(page.getByLabel(/^Total approved budget/)).toHaveCount(0);
  });

  test("unrelated employee cannot inspect the project", async ({ page }) => {
    await signIn(page, PERSONAS.associate.email);
    await page.goto(`/volunteering/projects?project=${projectId}`);
    await expect(page.getByRole("alert")).toContainText(/not a participant/);
    expect(
      (
        await api(page, workspaceService + "get_project", {
          project: projectId,
        })
      ).status,
    ).toBe(403);
  });

  test("later manager edits stay pending until the manager approves them", async ({
    page,
  }) => {
    await signIn(page, manager);
    await page.goto(`/volunteering/projects?project=${projectId}`);
    await page.getByRole("button", { name: "Propose changes" }).click();
    await page.getByLabel(/^Total approved budget/).fill("12000");
    await page
      .getByLabel("Reason for this proposal / change")
      .fill("Add the second delivery phase.");
    await page
      .getByRole("button", { name: "Save draft / edits" })
      .last()
      .click();
    await page
      .getByRole("button", { name: "Submit for project approval" })
      .click();
    const before = (
      await api(page, workspaceService + "get_project", {
        project: projectId,
      })
    ).data.message;
    expect(before.total_approved_budget).toBe(10000);
    await page.getByRole("button", { name: "Approve proposal" }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Approved" }),
    ).toBeVisible();
    const after = (
      await api(page, workspaceService + "get_project", {
        project: projectId,
      })
    ).data.message;
    expect(after.total_approved_budget).toBe(12000);
    expect(after.revisions).toHaveLength(2);
  });

  test("proposal page stays usable on a narrow mobile screen", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await signIn(page, proposer);
    await page.goto("/volunteering/projects?new=1");
    await expect(
      page.getByLabel("Project name *", { exact: true }),
    ).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      width: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width + 1);
  });
});
