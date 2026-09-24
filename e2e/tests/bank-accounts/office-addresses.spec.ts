import { expect, test, type Page } from "@playwright/test";
import { loginViaAPI } from "../../helpers/auth";
import { PERSONAS, type PersonaKey } from "../../helpers/personas";

const API = "volunteering.volunteering.office_addresses.";

async function signIn(page: Page, persona: PersonaKey) {
  await page.context().clearCookies();
  const credentials = PERSONAS[persona];
  await loginViaAPI(page.request, credentials.email, credentials.password);
  await page.goto("/volunteering/home");
  await expect(page.getByRole("heading", { name: /^Hello/ })).toBeVisible();
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
        // Permission failures can be HTML responses. Preserve the status so
        // the authorization assertion remains the source of truth.
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

test("employees view office addresses while Accounts Manager administers them", async ({
  page,
}) => {
  const title = `_Browser Office ${Date.now()}`;
  let addressName = "";

  await signIn(page, "accounts");
  await page.getByRole("link", { name: /Office addresses/ }).click();
  await expect(
    page.getByRole("heading", { name: "Office addresses", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add office address" }).click();
  await page.getByLabel("Address title *", { exact: true }).fill(title);
  await page
    .getByLabel("Address line 1 *", { exact: true })
    .fill("101 Local Browser Test Road");
  await page.getByLabel("City/Town *", { exact: true }).fill("Mumbai");
  await page.getByLabel("State/Province", { exact: true }).fill("Maharashtra");
  await page.getByLabel("Postal code", { exact: true }).fill("400001");
  await page.getByRole("button", { name: "Save address", exact: true }).click();
  const card = page.locator("article").filter({ hasText: title });
  await expect(card).toContainText("101 Local Browser Test Road");
  const managerWorkspace = (
    await api(page, API + "get_office_address_workspace")
  ).data.message;
  addressName = managerWorkspace.addresses.find(
    (row: any) => row.address_title === title,
  ).name;

  try {
    await signIn(page, "employee");
    await page.getByRole("link", { name: /Office addresses/ }).click();
    const employeeCard = page.locator("article").filter({ hasText: title });
    await expect(employeeCard).toContainText("101 Local Browser Test Road");
    await expect(
      page.getByRole("button", { name: "Add office address" }),
    ).toHaveCount(0);
    await expect(
      employeeCard.getByRole("button", { name: "Edit" }),
    ).toHaveCount(0);
    await expect(
      employeeCard.getByRole("button", { name: "Delete" }),
    ).toHaveCount(0);
    await page.goto("/volunteering/invoice-generator");
    const addressSelect = page.getByLabel("Office address *", {
      exact: true,
    });
    const optionValue = await addressSelect
      .locator("option")
      .filter({ hasText: title })
      .getAttribute("value");
    expect(optionValue).toBeTruthy();
    await addressSelect.selectOption(optionValue!);
    const office = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Sevamrita office" }),
    });
    await expect(office.locator("address")).toContainText(
      "101 Local Browser Test Road",
    );
    const denied = await api(page, API + "save_office_address", {
      details: {
        address_title: "Blocked employee office",
        address_type: "Office",
        address_line1: "Unauthorised Road",
        city: "Mumbai",
        country: "India",
      },
    });
    expect(denied.status, denied.body).toBe(403);
  } finally {
    if (addressName) {
      await signIn(page, "accounts");
      await page.getByRole("link", { name: /Office addresses/ }).click();
      const cleanupCard = page.locator("article").filter({ hasText: title });
      await expect(cleanupCard).toBeVisible();
      page.once("dialog", (dialog) => dialog.accept());
      await cleanupCard.getByRole("button", { name: "Delete" }).click();
      await expect(cleanupCard).toHaveCount(0);
    }
  }
});
