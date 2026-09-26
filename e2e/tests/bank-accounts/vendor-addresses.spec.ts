import { expect, test } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

test("generated invoice saves and reuses the employee's vendor address", async ({
  page,
  baseURL,
}) => {
  if (
    !baseURL ||
    !["127.0.0.1", "localhost", "sevamrita.local"].includes(
      new URL(baseURL).hostname,
    )
  ) {
    throw new Error("Vendor-address tests may only write to localhost.");
  }
  await loginViaAPI(
    page.request,
    PERSONAS.associate.email,
    PERSONAS.associate.password,
  );
  await page.goto("/volunteering/invoice-generator");

  const frequent = page.getByLabel("Frequent vendor address", {
    exact: true,
  });
  if (await frequent.count()) await frequent.selectOption("");

  const supplier = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Supplier", exact: true }),
  });
  await supplier
    .getByLabel("Legal name *", { exact: true })
    .fill("E2E Frequent Vendor");
  await supplier
    .getByLabel("Address *", { exact: true })
    .fill("91 Reusable Market Road, Pune");
  await supplier.getByLabel("State *", { exact: true }).fill("Maharashtra");
  await supplier.getByLabel("PIN code", { exact: true }).fill("411001");
  await supplier
    .getByLabel("PAN (optional)", { exact: true })
    .fill("ABCDE1234F");
  await page
    .getByLabel("Account holder name", { exact: true })
    .fill("E2E Frequent Vendor");
  await page
    .getByLabel("Bank name", { exact: true })
    .fill("Reusable Vendor Bank");
  await page
    .getByLabel("Account number", { exact: true })
    .fill("554433221100");
  await page.getByLabel("IFSC", { exact: true }).fill("TEST0123456");
  await page.getByLabel("UPI ID", { exact: true }).fill("vendor@example");
  await page
    .getByLabel("Description *", { exact: true })
    .fill("Reusable vendor address test");
  await page.getByLabel("Rate (INR) *", { exact: true }).fill("100");

  await page.getByRole("button", { name: "Sign freshly", exact: true }).click();
  const signatureCanvas = page.locator("canvas.signature-canvas");
  const signatureBox = await signatureCanvas.boundingBox();
  expect(signatureBox).toBeTruthy();
  await page.mouse.move(signatureBox!.x + 50, signatureBox!.y + 100);
  await page.mouse.down();
  await page.mouse.move(signatureBox!.x + 220, signatureBox!.y + 50, {
    steps: 8,
  });
  await page.mouse.move(signatureBox!.x + 400, signatureBox!.y + 120, {
    steps: 8,
  });
  await page.mouse.up();
  await page
    .getByRole("button", { name: "Use this signature", exact: true })
    .click();

  const responsePromise = page.waitForResponse((response) =>
    response.url().includes("generate_invoice_documents"),
  );
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Generate PDF", exact: true }).click();
  const generated = (await (await responsePromise).json()).message;
  expect(generated.invoice_style).toMatch(/^style-(0[1-9]|1[0-9]|20)$/);
  await downloadPromise;
  await expect(frequent).toBeVisible();
  await expect(frequent).toHaveValue(/.+/);

  await page.reload();
  const reloadedFrequent = page.getByLabel("Frequent vendor address", {
    exact: true,
  });
  const option = reloadedFrequent.locator("option", {
    hasText: "E2E Frequent Vendor",
  });
  await expect(option).toHaveCount(1);
  const savedValue = await option.getAttribute("value");
  expect(savedValue).toBeTruthy();
  await reloadedFrequent.selectOption(savedValue!);
  await expect(
    supplier.getByLabel("Legal name *", { exact: true }),
  ).toHaveValue("E2E Frequent Vendor");
  await expect(supplier.getByLabel("Address *", { exact: true })).toHaveValue(
    "91 Reusable Market Road, Pune",
  );
  await expect(supplier.getByLabel("State *", { exact: true })).toHaveValue(
    "Maharashtra",
  );
  await expect(
    page.getByLabel("Account holder name", { exact: true }),
  ).toHaveValue("E2E Frequent Vendor");
  await expect(page.getByLabel("Bank name", { exact: true })).toHaveValue(
    "Reusable Vendor Bank",
  );
  await expect(page.getByLabel("Account number", { exact: true })).toHaveValue(
    "554433221100",
  );
  await expect(page.getByLabel("IFSC", { exact: true })).toHaveValue(
    "TEST0123456",
  );
  await expect(page.getByLabel("UPI ID", { exact: true })).toHaveValue(
    "vendor@example",
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(reloadedFrequent).toBeVisible();
  await expect(
    supplier.getByLabel("Legal name *", { exact: true }),
  ).toBeVisible();
  await expect(supplier.getByLabel("Address *", { exact: true })).toBeVisible();
});
