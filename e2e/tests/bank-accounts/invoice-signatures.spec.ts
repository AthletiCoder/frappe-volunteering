import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

async function drawSignature(page: Page, buttonName: string) {
  await page.getByRole("button", { name: buttonName, exact: true }).click();
  const canvas = page.locator("canvas.signature-canvas");
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box).toBeTruthy();
  await page.mouse.move(box!.x + 60, box!.y + 120);
  await page.mouse.down();
  await page.mouse.move(box!.x + 180, box!.y + 55, { steps: 8 });
  await page.mouse.move(box!.x + 280, box!.y + 135, { steps: 8 });
  await page.mouse.move(box!.x + 430, box!.y + 50, { steps: 8 });
  await page.mouse.up();
  await page
    .getByRole("button", { name: "Use this signature", exact: true })
    .click();
}

async function fillRequiredInvoiceFields(page: Page) {
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
  await page
    .getByLabel("Description *", { exact: true })
    .fill("Local test utensils");
  await page.getByLabel("Rate (INR) *", { exact: true }).fill("500");
}

test("volunteer signature is mandatory and reusable while vendor signature is optional", async ({
  page,
  baseURL,
}, testInfo) => {
  if (
    !baseURL ||
    !["127.0.0.1", "localhost", "sevamrita.local"].includes(
      new URL(baseURL).hostname,
    )
  ) {
    throw new Error("Invoice generation demo tests may only write to localhost.");
  }
  await loginViaAPI(
    page.request,
    PERSONAS.associate.email,
    PERSONAS.associate.password,
  );
  const defaultsPromise = page.waitForResponse((response) =>
    response.url().includes("get_invoice_generator_defaults"),
  );
  await page.goto("/volunteering/invoice-generator");
  const defaults = (await (await defaultsPromise).json()).message;
  expect(defaults.volunteer.employee).toBe(defaults.employee);

  await fillRequiredInvoiceFields(page);

  await expect(
    page.getByRole("heading", {
      name: "Volunteer declaration and signature",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "I confirm that I paid the amount shown above and request reimbursement to my bank account.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Vendor will also sign this invoice")).not.toBeChecked();
  await expect(page.getByAltText("Vendor signature preview")).toHaveCount(0);

  await page.getByRole("button", { name: "Generate PDF", exact: true }).click();
  await expect(
    page.getByText("Add the volunteer signature before submitting this invoice.", {
      exact: true,
    }),
  ).toBeVisible();

  await drawSignature(page, "Sign freshly");
  await expect(page.getByAltText("Volunteer signature preview")).toBeVisible();

  const firstResponse = page.waitForResponse((response) =>
    response.url().includes("generate_invoice_documents"),
  );
  const firstDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Generate PDF", exact: true }).click();
  const firstHttpResponse = await firstResponse;
  const first = (await firstHttpResponse.json()).message;
  const firstPayload = firstHttpResponse.request().postDataJSON().payload;
  expect(first.vendor_signed).toBe(false);
  expect(firstPayload.volunteer_signature_data).toMatch(/^data:image\/png;base64,/);
  expect(firstPayload.vendor_will_sign).toBe(false);
  expect(firstPayload.vendor_signature_data).toBe("");
  await (await firstDownload).saveAs(testInfo.outputPath("volunteer-only.pdf"));

  await page.reload();
  await expect(
    page.getByText("A saved signature is available for reuse.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Use saved signature", exact: true })
    .click();
  await expect(page.getByText("Using saved signature", { exact: true })).toBeVisible();
  await fillRequiredInvoiceFields(page);

  await page.getByLabel("Vendor will also sign this invoice").check();
  await page
    .getByLabel("Vendor signatory name (optional)", { exact: true })
    .fill("Asha Vendor");
  await drawSignature(page, "Vendor sign on screen");
  await expect(page.getByAltText("Vendor signature preview")).toBeVisible();

  const secondResponse = page.waitForResponse((response) =>
    response.url().includes("generate_invoice_documents"),
  );
  const secondDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Generate Word", exact: true }).click();
  const secondHttpResponse = await secondResponse;
  const second = (await secondHttpResponse.json()).message;
  const secondPayload = secondHttpResponse.request().postDataJSON().payload;
  expect(second.vendor_signed).toBe(true);
  expect(secondPayload.volunteer_signature_data).toMatch(/^data:image\/png;base64,/);
  expect(secondPayload.vendor_signature_data).toMatch(/^data:image\/png;base64,/);
  await (await secondDownload).saveAs(
    testInfo.outputPath("volunteer-and-vendor.docx"),
  );
});
