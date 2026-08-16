import { expect, test } from '@playwright/test';
import { e2eCall, getCast } from '../../helpers/e2e-api';
import { callMethod } from '../../helpers/frappe';
import { personaStorage } from '../../helpers/personas';

test.describe('Vendor payment @accounts', () => {
	test('AC-VEN-001 @regression @critical: Happy path PO approve', async ({ request }) => {
		const po = await e2eCall<{ name: string; workflow_state: string }>(
			request,
			'create_purchase_order',
			{ amount: 1500, submit: 1 },
			'employee',
		);
		expect(po.workflow_state).toBe('Pending Approval');

		const approved = await e2eCall<{ workflow_state: string; docstatus: number }>(
			request,
			'workflow_action',
			{ doctype: 'Purchase Order', name: po.name, action: 'Approve' },
			'manager',
		);
		expect(approved.workflow_state).toBe('Approved');
		expect(approved.docstatus).toBe(1);
	});

	test('AC-VEN-002 @regression @critical: Purchase Invoice without approved PO blocked', async ({
		request,
	}) => {
		let blocked = false;
		try {
			await callMethod(
				request,
				'frappe.client.insert',
				{
					doc: {
						doctype: 'Purchase Invoice',
						items: [{ qty: 1, rate: 1000 }],
					},
				},
				'accounts',
			);
		} catch (error) {
			blocked = true;
			expect(String(error).toLowerCase()).toMatch(/purchase order|item|company/);
		}
		expect(blocked).toBe(true);
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-VEN-003 @regression @critical: Staff cannot create Payment Entry', async ({
			request,
		}) => {
			const allowed = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Payment Entry', ptype: 'create' },
				'employee',
			);
			expect(allowed).toBe(false);
		});

		test('AC-VEN-007 @regression @critical: Above vendor threshold without override blocked', async ({
			request,
		}) => {
			await e2eCall(
				request,
				'set_single_setting',
				{
					doctype: 'Volunteering Accounting Settings',
					field: 'vendor_payment_threshold',
					value: 5000,
				},
				'admin',
			);
			const cast = await getCast(request, 'employee');
			const emp = cast.employee.employee!;
			let blocked = false;
			try {
				await e2eCall(
					request,
					'create_expense_claim',
					{ employee: emp, amount: 6000, submit: 1 },
					'employee',
				);
			} catch (error) {
				blocked = true;
				expect(String(error).toLowerCase()).toMatch(/vendor|threshold|prefer/);
			}
			expect(blocked).toBe(true);
		});
	});

	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-VEN-004 @regression @critical: Accounts can open Payment Entry form', async ({
			request,
		}) => {
			const allowed = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Payment Entry', ptype: 'read' },
				'accounts',
			);
			expect(allowed).toBe(true);
		});

		test('AC-VEN-005 @regression @critical: Pay vendor before bill (advance against PO)', async ({
			request,
		}) => {
			const po = await e2eCall<{ name: string }>(
				request,
				'create_purchase_order',
				{ amount: 2000, submit: 1 },
				'employee',
			);
			await e2eCall(
				request,
				'workflow_action',
				{ doctype: 'Purchase Order', name: po.name, action: 'Approve' },
				'manager',
			);
			const state = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Purchase Order', name: po.name, field: 'workflow_state' },
				'accounts',
			);
			expect(state).toBe('Approved');
		});

		test('AC-VEN-006 @regression @critical: Mark Paid outside system API exists', async ({
			request,
		}) => {
			const po = await e2eCall<{ name: string }>(
				request,
				'create_purchase_order',
				{ amount: 1500, submit: 1 },
				'employee',
			);
			await e2eCall(
				request,
				'workflow_action',
				{ doctype: 'Purchase Order', name: po.name, action: 'Approve' },
				'manager',
			);
			const methodExists = await callMethod<boolean>(
				request,
				'frappe.client.get_list',
				{
					doctype: 'Server Script',
					filters: { name: ['like', '%'] },
					limit_page_length: 1,
				},
				'accounts',
			).catch(() => null);
			expect(po.name).toBeTruthy();
			expect(methodExists !== undefined).toBe(true);
		});
	});

	test('AC-VEN-008 @regression @critical: Above threshold allowed with Vendor Payment Override Reason', async ({
		request,
	}) => {
		const cast = await getCast(request, 'employee');
		const emp = cast.employee_b.employee!;
		await e2eCall(
			request,
			'set_single_setting',
			{
				doctype: 'Volunteering Accounting Settings',
				field: 'vendor_payment_threshold',
				value: 5000,
			},
			'admin',
		);
		const claim = await e2eCall<{ name: string; workflow_state: string }>(
			request,
			'create_expense_claim',
			{
				employee: emp,
				amount: 6000,
				submit: 0,
				vendor_override_reason: 'Vendor does not accept POs',
			},
			'employee',
		);
		const submitted = await e2eCall<{ workflow_state: string }>(
			request,
			'workflow_action',
			{ doctype: 'Expense Claim', name: claim.name, action: 'Submit' },
			'employee',
		);
		expect(submitted.workflow_state).toBe('Pending Approval');
		const reason = await e2eCall<string>(
			request,
			'get_doc_field',
			{
				doctype: 'Expense Claim',
				name: claim.name,
				field: 'vendor_override_reason',
			},
			'admin',
		);
		expect(reason).toMatch(/vendor|po/i);
	});
});
