import { expect, test } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS } from "../../helpers/personas";

test("optional invoice references are grouped in both GST and non-GST forms", async ({
  page,
}) => {
  await loginViaAPI(
    page.request,
    PERSONAS.associate.email,
    PERSONAS.associate.password,
  );
  await page.goto("/volunteering/invoice-generator");
  const optional = page.locator("details").filter({
    has: page.getByText("Optional fields (if available)", { exact: true }),
  });
  const summary = optional.locator("summary");
  const values = [
    ["Buyer order number", "PO-DEMO-001"],
    ["Buyer order date", "2026-09-15"],
    ["Supplier reference", "QUOTE-DEMO-001"],
    ["Dispatch document number", "DELIVERY-DEMO-001"],
    ["Delivery note date", "2026-09-16"],
  ];

  await expect(summary).toBeVisible();
  for (const type of ["Non-GST invoice", "GST tax invoice"]) {
    await page.getByRole("button", { name: new RegExp(`^${type}`) }).click();
    await expect(optional).not.toHaveAttribute("open", "");
    await expect(optional.locator("input")).toHaveCount(5);
    for (const [label] of values) {
      await expect(optional.getByLabel(label, { exact: true })).toBeHidden();
      await expect(
        optional.getByLabel(label, { exact: true }),
      ).not.toHaveAttribute("required", "");
    }

    // Native disclosure is keyboard accessible, and closing it keeps entered data.
    await summary.focus();
    await page.keyboard.press("Enter");
    for (const [label, value] of values) {
      const input = optional.getByLabel(label, { exact: true });
      await expect(input).toBeVisible();
      if (type === "Non-GST invoice") await input.fill(value);
      await expect(input).toHaveValue(value);
    }
    await summary.click();
    await expect(optional).not.toHaveAttribute("open", "");
    await expect(
      page.getByLabel("Invoice date *", { exact: true }),
    ).toBeVisible();
  }
});
