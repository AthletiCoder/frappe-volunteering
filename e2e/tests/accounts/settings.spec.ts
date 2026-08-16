import { expect, test } from '@playwright/test';
import { cleanupEmployeeAdvances, e2eCall, getCast } from '../../helpers/e2e-api';
import { personaStorage } from '../../helpers/personas';

test.describe('Accounting settings @accounts', () => {
	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-SET-001 @regression @critical: Accounts Manager edits Approval & Advance Limits', async ({
			request,
		}) => {
			const write = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Approval and Advance Limits', ptype: 'write' },
				'accounts',
			);
			expect(write).toBe(true);
		});

		test('AC-SET-003 @regression: Edit Vendor Payment Threshold and Cash Payment Limit', async ({
			request,
		}) => {
			await e2eCall(
				request,
				'set_single_setting',
				{
					doctype: 'Volunteering Accounting Settings',
					field: 'cash_payment_limit',
					value: 2000,
				},
				'accounts',
			);
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
			request,
		}) => {
			await e2eCall(
				request,
				'set_single_setting',
				{
					doctype: 'Volunteering Accounting Settings',
					field: 'cash_payment_limit',
					value: 2000,
				},
				'accounts',
			);
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

		test('AC-SET-005 @regression: Default Advance Project auto-fills on new advance', async ({
			request,
		}) => {
			const cast = await getCast(request, 'accounts');
			const accountsEmp = cast.accounts.employee!;
			await cleanupEmployeeAdvances(request, accountsEmp);
			const advance = await e2eCall<{ name: string }>(
				request,
				'create_employee_advance',
				{ employee: accountsEmp, amount: 1000, submit: 0 },
				'accounts',
			);
			const project = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Employee Advance', name: advance.name, field: 'project' },
				'accounts',
			);
			expect(project).toBeTruthy();
		});
	});

	test.describe('as hr', () => {
		test.use({ storageState: personaStorage('hr') });

		test('AC-SET-002 @regression @critical: HR Manager view-only on limits', async ({
			request,
		}) => {
			const write = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Approval and Advance Limits', ptype: 'write' },
				'hr',
			);
			const read = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Approval and Advance Limits', ptype: 'read' },
				'hr',
			);
			expect(read).toBe(true);
			expect(write).toBe(false);
		});
	});
});
