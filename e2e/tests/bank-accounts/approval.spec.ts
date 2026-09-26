import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

const API = "volunteering.volunteering.employee_bank_accounts.";
const employee = PERSONAS.associate.email;
const manager = PERSONAS.accounts.email;
const operator = "demo.accounts.user@sevamrita.local";
const number = "7000" + Date.now(); // Deliberately fictional local bank details.
let request: any;

function bankProof() {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(pdf));
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = Buffer.byteLength(pdf);
  pdf += "xref\n0 4\n0000000000 65535 f \n";
  pdf += offsets
    .slice(1)
    .map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`)
    .join("");
  pdf += `trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf);
}

async function signIn(page: Page, user: string) {
  await page.context().clearCookies();
  await loginViaAPI(page.request, user, PERSONAS.employee.password);
  await page.goto("/volunteering/home");
  await expect(page.getByRole("heading", { name: /^Hello/ })).toBeVisible();
}

async function addVolunteerSignature(page: Page) {
  await page.getByRole("button", { name: "Sign freshly", exact: true }).click();
  const canvas = page.locator("canvas.signature-canvas");
  const box = await canvas.boundingBox();
  expect(box).toBeTruthy();
  await page.mouse.move(box!.x + 50, box!.y + 100);
  await page.mouse.down();
  await page.mouse.move(box!.x + 220, box!.y + 50, { steps: 8 });
  await page.mouse.move(box!.x + 400, box!.y + 120, { steps: 8 });
  await page.mouse.up();
  await page.getByRole("button", { name: "Use this signature", exact: true }).click();
}

async function api(page: Page, method: string, args = {}) {
  return page.evaluate(
    async ({ method, args }) => {
      const response = await fetch(`/api/method/${method}`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-Frappe-CSRF-Token": (window as any).csrf_token || "",
        },
        body: JSON.stringify(args),
      });
      const body = await response.text();
      let data = null;
      try {
        data = JSON.parse(body);
      } catch {
        // Frappe may render permission failures as HTML. These security tests
        // assert the HTTP status and must not hide it behind a JSON parse error.
      }
      return {
        status: response.status,
        data,
        body: data ? "" : body.slice(0, 1000),
      };
    },
    { method, args },
  );
}

test.describe.serial("Employee bank approval @bank-accounts @ui", () => {
  test.beforeAll(async ({ baseURL }) => {
    if (
      !baseURL ||
      !["127.0.0.1", "localhost", "sevamrita.local"].includes(
        new URL(baseURL).hostname,
      )
    ) {
      throw new Error("Bank-account demo tests may only write to localhost.");
    }
  });

  test("employee submits proof from Home and sees only masked history", async ({
    page,
  }) => {
    await signIn(page, employee);
    const existingWorkspace = (
      await api(page, API + "get_bank_account_workspace")
    ).data.message;
    const stalePending = existingWorkspace.requests.find(
      (row: any) => row.request_status === "Pending Approval",
    );
    if (stalePending) {
      await signIn(page, manager);
      const cleanup = await api(page, API + "review_bank_account_request", {
        request: stalePending.name,
        action: "reject",
        modified: stalePending.modified,
        comments: "Superseded by a fresh local browser-test request.",
      });
      expect(cleanup.status, cleanup.body).toBe(200);
      await signIn(page, employee);
    }
    await page
      .getByRole("link", { name: /My reimbursement bank account/ })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Reimbursement bank account",
        exact: true,
      }),
    ).toBeVisible();
    await page
      .getByLabel("Account-holder name *", { exact: true })
      .fill("Local Demo Associate");
    await page
      .getByLabel("Bank name *", { exact: true })
      .fill("Demo Reimbursement Bank");
    await page.getByLabel("Branch", { exact: true }).fill("Local test branch");
    await page.getByLabel("IFSC *", { exact: true }).fill("TEST0123456");
    await page.getByLabel("Account number *", { exact: true }).fill(number);
    await page
      .getByLabel("Re-enter account number *", { exact: true })
      .fill(number);
    await page.getByLabel(/^Cancelled cheque or bank proof/).setInputFiles({
      name: "local-bank-proof.pdf",
      mimeType: "application/pdf",
      buffer: bankProof(),
    });
    await page.getByLabel(/^I confirm this account belongs/).check();
    await page
      .getByRole("button", { name: "Submit for approval", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText(
      "Bank details submitted",
    );
    const workspace = (await api(page, API + "get_bank_account_workspace")).data
      .message;
    request = workspace.requests.find(
      (row: any) => row.request_status === "Pending Approval",
    );
    expect(request).toBeTruthy();
    expect(request).not.toHaveProperty("account_number");
    expect(request.account_number_masked).toBe("••••••" + number.slice(-4));
    expect(workspace.pending_requests).toEqual([]);
    expect((await page.request.get(request.proof_url)).status()).toBe(200);
    await page.goto("/volunteering/invoice-generator");
    await expect(
      page.getByRole("button", { name: "Generate PDF", exact: true }),
    ).toBeEnabled();
  });

  test("Accounts User cannot review or download another employee's bank proof", async ({
    page,
  }) => {
    await signIn(page, operator);
    await expect(
      page.getByRole("link", { name: /Review reimbursement bank accounts/ }),
    ).toHaveCount(0);
    await page.goto("/volunteering/bank-account");
    await expect(
      page.getByRole("heading", { name: "Accounts Manager review queue" }),
    ).toHaveCount(0);
    const denied = await api(page, API + "review_bank_account_request", {
      request: request.name,
      action: "approve",
      modified: request.modified,
    });
    expect(denied.status, denied.body).toBe(403);
    expect((await page.request.get(request.proof_url)).status()).toBe(403);
  });

  test("Accounts Manager reviews proof and approves through Home", async ({
    page,
  }) => {
    await signIn(page, manager);
    await page
      .getByRole("link", { name: /Review reimbursement bank accounts/ })
      .click();
    const card = page.locator("article").filter({ hasText: request.name });
    await expect(card).toContainText(number);
    expect((await page.request.get(request.proof_url)).status()).toBe(200);
    await card
      .getByLabel("Review comments")
      .fill("Verified fictional local demonstration bank proof");
    await card
      .getByRole("button", { name: "Approve account", exact: true })
      .click();
    await expect(card).toHaveCount(0);
  });

  test("employee generates GST and non-GST PDF/Word using optional supplier remittance", async ({
    page,
  }, testInfo) => {
    await signIn(page, employee);
    await page.getByRole("link", { name: /Prepare an invoice/ }).click();
    await expect(
      page.getByRole("heading", {
        name: "Supplier bank details (optional)",
      }),
    ).toBeVisible();
    await expect(
      page.getByText("••••••" + number.slice(-4), { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByLabel("Invoice number", { exact: true }),
    ).toHaveAttribute("readonly", "");
    await expect(
      page.getByLabel("Invoice number", { exact: true }),
    ).toHaveValue("Assigned automatically on generation");
    const supplier = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Supplier", exact: true }),
    });
    await supplier
      .getByLabel("Legal name *", { exact: true })
      .fill("Demo Kitchen Supplies");
    await supplier
      .getByLabel("Address *", { exact: true })
      .fill("12 Demo Market Road, Mumbai");
    await supplier.getByLabel("State *", { exact: true }).fill("Maharashtra");
    await expect(
      supplier.getByLabel("PAN (optional)", { exact: true }),
    ).not.toHaveAttribute("required", "");
    const office = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Sevamrita office" }),
    });
    await expect(
      office.getByLabel("Office address *", { exact: true }),
    ).not.toHaveValue("");
    await expect(office.locator("address")).not.toHaveText("");
    await page
      .getByLabel("Account holder name", { exact: true })
      .fill("Demo Kitchen Supplies");
    await page
      .getByLabel("Bank name", { exact: true })
      .fill("Demo Vendor Bank");
    await page
      .getByLabel("Account number", { exact: true })
      .fill("880012345678");
    await page.getByLabel("IFSC", { exact: true }).fill("DEMO0123456");
    await page
      .getByLabel("Description *", { exact: true })
      .fill("Local test utensils");
    await page.getByLabel("HSN/SAC (optional)", { exact: true }).fill("7323");
    await page.getByLabel("Rate (INR) *", { exact: true }).fill("500");
    await addVolunteerSignature(page);
    let previousNumber: string | undefined;
    let generationPayload: any;
    for (const type of ["NON_GST", "GST"]) {
      if (type === "GST") {
        await page.getByRole("button", { name: /^GST tax invoice/ }).click();
        await supplier
          .getByLabel("GSTIN *", { exact: true })
          .fill("27ABCDE1234F1Z5");
        await page.getByLabel("GST amount", { exact: true }).fill("90");
      }
      let invoiceNumber: string | undefined;
      for (const [button, extension] of [
        ["Generate PDF", "pdf"],
        ["Generate Word", "docx"],
      ]) {
        const responsePromise = page.waitForResponse((response) =>
          response.url().includes("generate_invoice_documents"),
        );
        const downloadPromise = page.waitForEvent("download");
        await page.getByRole("button", { name: button, exact: true }).click();
        const response = await responsePromise;
        expect(response.status()).toBe(200);
        const generated = (await response.json()).message;
        generationPayload = response.request().postDataJSON().payload;
        expect(generationPayload.bank).toMatchObject({
          account_name: "Demo Kitchen Supplies",
          bank_name: "Demo Vendor Bank",
          account_number: "880012345678",
          ifsc: "DEMO0123456",
        });
        expect(response.request().postDataJSON().output_format).toBe(extension);
        expect(generated).toHaveProperty(extension);
        expect(generated).not.toHaveProperty(
          extension === "pdf" ? "docx" : "pdf",
        );
        expect(generated.invoice_number).toMatch(/^INV-\d{4}-\d{6,7}$/);
        if (invoiceNumber) {
          expect(generated.invoice_number).toBe(invoiceNumber);
        } else {
          if (previousNumber) {
            expect(Number(generated.invoice_number.slice(9))).toBe(
              Number(previousNumber.slice(9)) + 1,
            );
          }
          invoiceNumber = generated.invoice_number;
        }
        await expect(
          page.getByLabel("Invoice number", { exact: true }),
        ).toHaveValue(generated.invoice_number);
        const download = await downloadPromise;
        expect(download.suggestedFilename()).toBe(
          `invoice-${generated.invoice_number}.${extension}`,
        );
        await download.saveAs(testInfo.outputPath(`${type}.${extension}`));
      }
      previousNumber = invoiceNumber;
    }
    // Two successful overlapping requests must never get the same number.
    generationPayload.invoice_number = "FORGED-BROWSER-NUMBER";
    const parallel = await Promise.all(
      [1, 2].map(() =>
        api(
          page,
          "volunteering.volunteering.invoice_generator.generate_invoice_documents",
          {
            payload: generationPayload,
          },
        ),
      ),
    );
    expect(
      parallel.map((result) => ({
        status: result.status,
        ...(result.status !== 200
          ? { error: result.data.exception, trace: result.data.exc }
          : {}),
      })),
    ).toEqual([{ status: 200 }, { status: 200 }]);
    const allocated = parallel
      .map((result) => result.data.message.invoice_number as string)
      .sort();
    expect(new Set(allocated).size).toBe(2);
    expect(allocated.map((value) => Number(value.slice(9)))).toEqual([
      Number(previousNumber!.slice(9)) + 1,
      Number(previousNumber!.slice(9)) + 2,
    ]);
  });
});
