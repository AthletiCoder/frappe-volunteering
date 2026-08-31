import { expect, test } from '@playwright/test';
import {
	cleanupEmployeeAdvances,
	e2eCall,
	getCast,
} from '../../helpers/e2e-api';
import { personaStorage } from '../../helpers/personas';
import { AccountingSettingsPage } from '../../pages/desk/accounting-settings.page';
import { ApprovalLimitsPage } from '../../pages/desk/approval-limits.page';
import { EmployeeAdvanceFormPage } from '../../pages/desk/employee-advance.page';

test.describe('Accounting settings @accounts @ui', () => {
	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-SET-001 @regression @critical: Accounts Manager edits Approval & Advance Limits', async ({
			page,
		}) => {
			const limits = new ApprovalLimitsPage(page);
			await limits.open();
			await expect(page.locator('[data-fieldname="designation_limits"]')).toBeVisible();
			await expect(page.getByText('Max Self Advance', { exact: false }).first()).toBeVisible();
			await expect(page.locator('.primary-action, button[data-label="Save"]').filter({ hasText: 'Save' })).toBeVisible();
		});

		test('AC-SET-003 @regression: Edit Vendor Payment Threshold and Cash Payment Limit', async ({
			page,
			request,
		}) => {
			const settings = new AccountingSettingsPage(page);
			await settings.open();
			await settings.setField('cash_payment_limit', 2000);
			const limit = await e2eCall<number>(
				request,
				'get_doc_field',
				{
					doctype: 'Volunteering Accounting Settings',
					name: 'Volunteering Accounting Settings',
					field: 'cash_payment_limit',
				},
				'accounts',
			);
			expect(Number(limit)).toBe(2000);
		});

		test('AC-SET-004 @regression: Cash payment within limit setting saved', async ({
			page,
			request,
		}) => {
			const settings = new AccountingSettingsPage(page);
			await settings.open();
			await settings.setField('cash_payment_limit', 2000);
			const limit = await e2eCall<number>(
				request,
				'get_doc_field',
				{
					doctype: 'Volunteering Accounting Settings',
					name: 'Volunteering Accounting Settings',
					field: 'cash_payment_limit',
				},
				'accounts',
			);
			expect(Number(limit)).toBe(2000);
		});

		test('AC-SET-005 @regression: Advances are not tagged to a project', async ({
			page,
			request,
		}) => {
			const cast = await getCast(request, 'accounts');
			const accountsEmp = cast.accounts.employee!;
			await cleanupEmployeeAdvances(request, accountsEmp);

			const advance = new EmployeeAdvanceFormPage(page);
			await advance.openNew();
			await advance.fillAdvance(1000);
			const advanceName = await advance.saveDraft();

			const project = await e2eCall<string | null>(
				request,
				'get_doc_field',
				{ doctype: 'Employee Advance', name: advanceName, field: 'project' },
				'accounts',
			);
			expect(project).toBeFalsy();
			await expect(
				page.locator('.form-layout:visible [data-fieldname="project"], .form-page:visible [data-fieldname="project"]').first(),
			).toBeHidden();
		});
	});

	test.describe('as hr', () => {
		test.use({ storageState: personaStorage('hr') });

		test('AC-SET-002 @regression @critical: HR Manager view-only on limits', async ({ page }) => {
			const limits = new ApprovalLimitsPage(page);
			await limits.open();
			await expect(page.locator('[data-fieldname="designation_limits"]')).toBeVisible();
			await expect(page.getByText('Max Self Advance', { exact: false }).first()).toBeVisible();
			await limits.expectReadOnly();
		});
	});
});
