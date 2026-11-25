import fs from 'node:fs';
import { expect, test } from '@playwright/test';

const fixturePath = process.env.E2E_HR_FIXTURES;
const fixture = fixturePath ? JSON.parse(fs.readFileSync(fixturePath, 'utf8')) : null;
test.skip(!fixture, 'Requires isolated local HR fixtures.');
test.beforeEach(({ baseURL }) => {
  if (!baseURL || !['127.0.0.1', 'localhost'].includes(new URL(baseURL).hostname)) {
    throw new Error('Use an isolated local site for HR layout tests.');
  }
});

for (const width of [320, 390, 1440]) {
  test.describe(`${width}px leave request layout`, () => {
    test.use({ viewport: { width, height: 900 } });
    test('balance labels, compact date controls and cancellation remain usable', async ({ page }) => {
      const account = fixture.users.employee;
      expect((await page.request.post('/api/method/login', {
        form: { usr: account.email, pwd: account.password },
      })).ok()).toBeTruthy();
      await page.goto('/volunteering/time-leave');
      await expect(page.getByText('Paid leave remaining', { exact: true })).toBeVisible();
      await expect(page.getByText('Compensatory leave remaining', { exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'New request', exact: true }).click();
      const from = await page.getByLabel('From date', { exact: true }).boundingBox();
      const to = await page.getByLabel('To date', { exact: true }).boundingBox();
      expect(from).not.toBeNull(); expect(to).not.toBeNull();
      if (width >= 390) {
        expect(Math.abs(from!.y - to!.y)).toBeLessThan(2);
        expect(to!.x).toBeGreaterThan(from!.x + from!.width);
      } else {
        expect(to!.y).toBeGreaterThan(from!.y + from!.height);
      }
      await page.getByLabel('Include a half day', { exact: true }).check();
      await expect(page.getByLabel('Half-day date', { exact: true })).toBeVisible();
      await page.getByLabel('Request type', { exact: true }).selectOption('Paternity Leave');
      await expect(page.getByLabel('Half-day date', { exact: true })).toHaveCount(0);
      await expect(page.getByLabel('Expected or actual childbirth date', { exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
      await page.screenshot({ path: `output/compact-leave-20261125/web-${width}.png`, fullPage: true });
      await page.getByRole('button', { name: 'Cancel', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'New request', exact: true })).toHaveCount(0);
    });

  });
}
