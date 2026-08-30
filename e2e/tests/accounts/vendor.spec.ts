import { expect, test } from '@playwright/test';
import {
	cleanupExpenseClaimsForProject,
	cleanupPurchaseOrdersForProject,
	e2eCall,
} from '../../helpers/e2e-api';
import { expectFormError } from '../../helpers/dialogs';
import { withPersona } from '../../helpers/persona-context';
import { personaStorage } from '../../helpers/personas';
import { getE2eMasters, getE2eProject } from '../../helpers/ui-fixtures';
import { ExpenseClaimFormPage } from '../../pages/desk/expense-claim.page';
import { PaymentEntryFormPage } from '../../pages/desk/payment-entry.page';
import { PurchaseInvoiceFormPage } from '../../pages/desk/purchase-invoice.page';
import { PurchaseOrderFormPage } from '../../pages/desk/purchase-order.page';

test.describe('Vendor payment @accounts @ui', () => {
	async function prepareVendorProject(request: import('@playwright/test').APIRequestContext) {
		const project = await getE2eProject(request);
		await cleanupPurchaseOrdersForProject(request, project);
		await cleanupExpenseClaimsForProject(request, project);
		return project;
	}

	test('AC-VEN-001 @regression @critical: Happy path PO approve', async ({ browser, request }) => {
		const project = await prepareVendorProject(request);
		const masters = await getE2eMasters(request);

		let poName = '';
		await withPersona(browser, 'employee', async (page) => {
			const po = new PurchaseOrderFormPage(page);
			await po.openNew();
			await po.fillPo({
				supplier: masters.supplier,
				project,
				amount: 1500,
				itemCode: masters.item_code,
			});
			poName = await po.saveAndSubmit();
		});

		const workflowState = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Purchase Order', name: poName, field: 'workflow_state' },
			'admin',
		);
		expect(workflowState).toBe('Pending Approval');

		await withPersona(browser, 'manager', async (page) => {
			const po = new PurchaseOrderFormPage(page);
			await po.open(poName);
			await po.approve();
		});

		const approvedState = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Purchase Order', name: poName, field: 'workflow_state' },
			'admin',
		);
		const docstatus = await e2eCall<number>(
			request,
			'get_doc_field',
			{ doctype: 'Purchase Order', name: poName, field: 'docstatus' },
			'admin',
		);
		expect(approvedState).toBe('Approved');
		expect(docstatus).toBe(1);
	});

	test('AC-VEN-002 @regression @critical: Purchase Invoice without approved PO blocked', async ({
		browser,
		request,
	}) => {
		const project = await prepareVendorProject(request);
		const masters = await getE2eMasters(request);

		await withPersona(browser, 'accounts', async (page) => {
			const pi = new PurchaseInvoiceFormPage(page);
			await pi.openNew();
			await pi.save({ expectError: /purchase order|supplier|required|mandatory|item/i });
		});

		let pendingPoName = '';
		await withPersona(browser, 'employee', async (page) => {
			const po = new PurchaseOrderFormPage(page);
			await po.openNew();
			await po.fillPo({
				supplier: masters.supplier,
				project,
				amount: 1200,
				itemCode: masters.item_code,
			});
			pendingPoName = await po.saveAndSubmit();
		});

		await withPersona(browser, 'accounts', async (page) => {
			const pi = new PurchaseInvoiceFormPage(page);
			await pi.createFromPo(pendingPoName);
			await pi.saveDraft();
			await pi.submit({
				expectError: /not approved|submitted|purchase order|docstatus|cannot map/i,
			});
		});
	});

	test.describe('as employee', () => {
		test.use({ storageState: personaStorage('employee') });

		test('AC-VEN-003 @regression @critical: Staff cannot create Payment Entry', async ({
			page,
			request,
			browser,
		}) => {
			const pe = new PaymentEntryFormPage(page);
			await pe.expectFormBlocked();

			const project = await getE2eProject(request);
			const masters = await getE2eMasters(request);

			let poName = '';
			await withPersona(browser, 'employee', async (empPage) => {
				const po = new PurchaseOrderFormPage(empPage);
				await po.openNew();
				await po.fillPo({
					supplier: masters.supplier,
					project,
					amount: 1500,
					itemCode: masters.item_code,
				});
				poName = await po.saveAndSubmit();
			});

			await withPersona(browser, 'manager', async (mgrPage) => {
				const po = new PurchaseOrderFormPage(mgrPage);
				await po.open(poName);
				await po.approve();
			});

			await pe.openNew();
			await pe.expectFormBlocked();
		});

		test('AC-VEN-007 @regression @critical: Above vendor threshold without override blocked', async ({
			page,
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
			const project = await getE2eProject(request);
			const masters = await getE2eMasters(request);

			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 6000,
				expenseType: masters.expense_type,
			});
			await claim.saveExpectVendorWarning();
		});
	});

	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-VEN-004 @regression @critical: Accounts can open Payment Entry form', async ({
			page,
		}) => {
			const pe = new PaymentEntryFormPage(page);
			await pe.expectFormReachable();
		});

		test('AC-VEN-005 @regression @critical: Pay vendor before bill (advance against PO)', async ({
			page,
			request,
			browser,
		}) => {
			const project = await prepareVendorProject(request);
			const masters = await getE2eMasters(request);

			let poName = '';
			await withPersona(browser, 'employee', async (empPage) => {
				const po = new PurchaseOrderFormPage(empPage);
				await po.openNew();
				await po.fillPo({
					supplier: masters.supplier,
					project,
					amount: 2000,
					itemCode: masters.item_code,
				});
				poName = await po.saveAndSubmit();
			});

			await withPersona(browser, 'manager', async (mgrPage) => {
				const po = new PurchaseOrderFormPage(mgrPage);
				await po.open(poName);
				await po.approve();
			});

			const po = new PurchaseOrderFormPage(page);
			await po.open(poName);
			const peName = await po.createPaymentEntry();

			const docstatus = await e2eCall<number>(
				request,
				'get_doc_field',
				{ doctype: 'Payment Entry', name: peName, field: 'docstatus' },
				'accounts',
			);
			const partyType = await e2eCall<string>(
				request,
				'get_doc_field',
				{ doctype: 'Payment Entry', name: peName, field: 'party_type' },
				'accounts',
			);
			expect(peName).toBeTruthy();
			expect(docstatus).toBe(1);
			expect(partyType).toBe('Supplier');
		});

		test('AC-VEN-006 @regression @critical: Mark Paid outside system creates Payment Entry', async ({
			page,
			request,
			browser,
		}) => {
			const project = await prepareVendorProject(request);
			const masters = await getE2eMasters(request);

			let poName = '';
			await withPersona(browser, 'employee', async (empPage) => {
				const po = new PurchaseOrderFormPage(empPage);
				await po.openNew();
				await po.fillPo({
					supplier: masters.supplier,
					project,
					amount: 1500,
					itemCode: masters.item_code,
				});
				poName = await po.saveAndSubmit();
			});

			await withPersona(browser, 'manager', async (mgrPage) => {
				const po = new PurchaseOrderFormPage(mgrPage);
				await po.open(poName);
				await po.approve();
			});

			let piName = '';
			await withPersona(browser, 'accounts', async (acctPage) => {
				const pi = new PurchaseInvoiceFormPage(acctPage);
				await pi.createFromPo(poName);
				piName = await pi.saveAndSubmit();
			});

			const piDocstatus = await e2eCall<number>(
				request,
				'get_doc_field',
				{ doctype: 'Purchase Invoice', name: piName, field: 'docstatus' },
				'accounts',
			);
			expect(piDocstatus).toBe(1);

			const pi = new PurchaseInvoiceFormPage(page);
			await pi.open(piName);
			await pi.markPaidOutside('E2E cash to vendor');

			const outstanding = await e2eCall<number>(
				request,
				'get_doc_field',
				{ doctype: 'Purchase Invoice', name: piName, field: 'outstanding_amount' },
				'accounts',
			);
			expect(Number(outstanding)).toBe(0);
		});
	});

	test('AC-VEN-008 @regression @critical: Above threshold allowed with Vendor Payment Override Reason', async ({
		browser,
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
		const project = await getE2eProject(request);
		const masters = await getE2eMasters(request);

		let claimName = '';
		await withPersona(browser, 'employee_b', async (page) => {
			const claim = new ExpenseClaimFormPage(page);
			await claim.openNew();
			await claim.fillClaim({
				project,
				amount: 6000,
				expenseType: masters.expense_type,
				vendorOverrideReason: 'Vendor does not accept POs',
			});
			claimName = await claim.saveAndSubmit(request);
		});

		const workflowState = await e2eCall<string>(
			request,
			'get_doc_field',
			{ doctype: 'Expense Claim', name: claimName, field: 'workflow_state' },
			'admin',
		);
		expect(workflowState).toBe('Pending Approval');

		const reason = await e2eCall<string>(
			request,
			'get_doc_field',
			{
				doctype: 'Expense Claim',
				name: claimName,
				field: 'vendor_override_reason',
			},
			'admin',
		);
		expect(reason).toMatch(/vendor|po/i);
	});
});
