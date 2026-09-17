import { expect, test } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

test("supplier and volunteer signing generate distinct GST/non-GST documents", async ({
  page,
  baseURL,
}, testInfo) => {
  if (
    !baseURL ||
    !["127.0.0.1", "localhost", "sevamrita.local"].includes(
      new URL(baseURL).hostname,
    )
  ) {
    throw new Error(
      "Invoice generation demo tests may only write to localhost.",
    );
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
  expect(defaults.has_approved_bank).toBe(true);
  await expect(
    page.getByText("Supplier confirmation is mandatory", { exact: true }),
  ).toHaveCount(0);
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
  const consignee = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Consignee and buyer" }),
  });
  await expect(
    consignee.getByLabel("Consignee office address *", { exact: true }),
  ).toHaveValue(defaults.default_office_address);
  await expect(
    consignee.getByLabel("Address *", { exact: true }),
  ).toHaveAttribute("readonly", "");
  await page
    .getByLabel("Description *", { exact: true })
    .fill("Local test utensils");
  // Leave HSN/SAC blank and generate both formats for both signer/invoice choices.
  const hsn = page.getByLabel("HSN/SAC (optional)", { exact: true });
  await expect(hsn).not.toHaveAttribute("required", "");
  await expect(hsn).toHaveValue("");
  await expect(
    page.getByText("I will obtain supplier verification and signature.", {
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByText("I will verify the details and sign as the volunteer.", {
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByText(
      "Generating a file does not sign it or approve reimbursement.",
      { exact: true },
    ),
  ).toHaveCount(0);
  await page.getByLabel("Rate (INR) *", { exact: true }).fill("500");

  const numbers = new Set<string>();
  for (const signer of ["SUPPLIER", "VOLUNTEER"]) {
    await page
      .getByLabel("Who will sign? *", { exact: true })
      .selectOption(signer);
    for (const type of ["NON_GST", "GST"]) {
      await page
        .getByRole("button", {
          name: type === "GST" ? /^GST tax invoice/ : /^Non-GST invoice/,
        })
        .click();
      if (type === "GST") {
        await supplier
          .getByLabel("GSTIN *", { exact: true })
          .fill("27ABCDE1234F1Z5");
        await page
          .getByLabel("Place of supply *", { exact: true })
          .fill("Maharashtra");
      }
      const declaration = page.getByRole("heading", {
        name: "Non-GST declaration",
        exact: true,
      });
      await expect(declaration).toHaveCount(0);
      if (signer === "VOLUNTEER") {
        await expect(
          page.getByLabel("Volunteer name", { exact: true }),
        ).toHaveValue(defaults.volunteer.name);
        await expect(
          page.getByLabel("Volunteer name", { exact: true }),
        ).toHaveAttribute("readonly", "");
        await expect(
          page.getByLabel("Supplier signatory name", { exact: true }),
        ).toHaveCount(0);
      } else {
        await page
          .getByLabel("Supplier signatory name", { exact: true })
          .fill("Asha Vendor");
      }
      let number: string | undefined;
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
        expect(generated.signer_type).toBe(signer);
        const payload = response.request().postDataJSON().payload;
        expect(payload.items[0].hsn_sac).toBe("");
        expect(payload).not.toHaveProperty("signature_confirmation_required");
        expect(payload).not.toHaveProperty("supplier_confirmation_required");
        if (number) expect(generated.invoice_number).toBe(number);
        else {
          expect(numbers.has(generated.invoice_number)).toBe(false);
          numbers.add(generated.invoice_number);
          number = generated.invoice_number;
        }
        const download = await downloadPromise;
        await download.saveAs(
          testInfo.outputPath(`${signer}-${type}.${extension}`),
        );
      }
    }
  }
  expect(numbers.size).toBe(4);
});
