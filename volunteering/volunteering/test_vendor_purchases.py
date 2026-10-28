"""Exercise real purchasing documents, permissions, dates and ledger effects."""
import base64
from io import BytesIO
from uuid import uuid4

from pypdf import PdfWriter

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from volunteering.volunteering.accounting_setup import setup_accounting_custom_fields
from volunteering.volunteering.accounting_test_utils import (
	get_or_create_user, get_or_create_employee, get_or_create_department,
	get_or_create_project_with_cost_center, get_or_create_expense_account,
	mute_accounting_test_emails, save_test_project, set_employee_grade,
)
from volunteering.volunteering.vendor_purchases import (
	KEY, configure_vendor_advances, create_purchase_master, get_purchase,
	get_purchase_workspace, record_goods_received, record_supplier_invoice,
	record_vendor_payment, review_purchase, save_purchase,
)


class IntegrationTestVendorPurchases(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.emails = mute_accounting_test_emails()
		setup_accounting_custom_fields()
		cls.requester = get_or_create_user("purchase-home-employee@example.com", ["Employee"], "Arjun Purchase")
		cls.manager = get_or_create_user("purchase-home-manager@example.com", ["Employee", "Expense Approver"], "Vikram Purchase")
		cls.accounts = get_or_create_user("purchase-home-accounts@example.com", ["Employee", "Accounts Manager"], "Nikhil Accounts")
		cls.other = get_or_create_user("purchase-home-other@example.com", ["Employee"], "Other Employee")
		department = get_or_create_department("Purchase Home Tests")
		manager = get_or_create_employee(cls.manager, department, "Vikram")
		employee = get_or_create_employee(cls.requester, department, "Arjun")
		get_or_create_employee(cls.other, department, "Ravi")
		get_or_create_employee(cls.accounts, department, "Nikhil")
		set_employee_grade(manager, "Board of Directors")
		set_employee_grade(employee, "Associate", reports_to=manager)
		cls.project = get_or_create_project_with_cost_center()
		cls.expense = get_or_create_expense_account()
		cls.company = frappe.db.get_value("Project", cls.project, "company")
		cls.cash = frappe.db.get_value("Account", {"company": cls.company, "account_type": "Cash", "is_group": 0, "disabled": 0}, "name")
		# Never depend on, overdraw or modify a real/demo bank during tests.
		parent_bank = frappe.db.get_value("Account", {"company": cls.company, "account_type": "Bank", "is_group": 0, "disabled": 0}, "parent_account")
		cls.bank = frappe.get_doc({"doctype": "Account", "account_name": "_Home Purchase Test Bank " + str(uuid4())[:8], "company": cls.company, "parent_account": parent_bank, "account_type": "Bank", "account_currency": "INR", "balance_must_be": "Debit"}).insert().name
		opening = frappe.db.get_value("Account", {"company": cls.company, "account_type": "Temporary", "is_group": 0, "disabled": 0}, "name")
		frappe.get_doc({"doctype": "Journal Entry", "company": cls.company, "voucher_type": "Opening Entry", "is_opening": "Yes", "posting_date": nowdate(), "user_remark": "Rollback-only purchasing test fixture funding", "accounts": [{"account": cls.bank, "debit_in_account_currency": 1000000}, {"account": opening, "credit_in_account_currency": 1000000}]}).insert().submit()
		cls.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		if not cls.supplier:
			cls.supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Purchase Home Test Supplier", "supplier_type": "Company", "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")}).insert().name
		cls.item = "_Home Purchase Consumption"
		if not frappe.db.exists("Item", cls.item):
			frappe.get_doc({"doctype": "Item", "item_code": cls.item, "item_name": "Kitchen materials", "is_stock_item": 0, "is_purchase_item": 1, "stock_uom": "Nos", "item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")}).insert()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		cls.emails.close()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.savepoint = "purchase_" + uuid4().hex
		frappe.db.savepoint(self.savepoint)
		project = frappe.get_doc("Project", self.project)
		project.project_setup_version = 1
		project.project_owner = self.manager
		project.project_purpose = "Purchase kitchen materials for the community meal programme"
		project.operational_status = "Active"
		project.budget_status = "Active"
		project.project_budget_control = "No Control"
		project.account_budget_control = "No Control"
		project.is_archived = 0
		if self.requester not in [row.user for row in project.project_participants]:
			project.append("project_participants", {"user": self.requester, "access_level": "Basic"})
		save_test_project(project)
		frappe.db.set_single_value("Volunteering Accounting Settings", "use_grade_approval", 1)
		frappe.set_user(self.accounts)
		configure_vendor_advances()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=self.savepoint)
		frappe.clear_cache()
		super().tearDown()

	def payload(self, amount=1000):
		return {"request_key": str(uuid4()), "supplier": self.supplier, "project": self.project, "transaction_date": add_days(nowdate(), -2), "schedule_date": nowdate(), "terms": "Kitchen materials for community meals", "items": [{"item_code": self.item, "qty": 10, "rate": amount / 10}]}

	def approved_order(self, amount=1000):
		frappe.set_user(self.requester)
		order = save_purchase(self.payload(amount), submit=1)
		frappe.set_user(self.manager)
		return review_purchase(order["name"], "Approve", order["modified"])

	def payment(self, amount, **overrides):
		return {"request_key": str(uuid4()), "amount": amount, "paid_from": self.bank, "posting_date": nowdate(), "reference_no": "PURCHASE-TEST-" + str(uuid4())[:8], "reference_date": nowdate(), **overrides}

	def receipt(self, order, qty=10):
		return record_goods_received(order["name"], {"request_key": str(uuid4()), "posting_date": nowdate(), "items": [{"order_item": order["items"][0]["name"], "qty": qty}]})

	def invoice(self, order, receipt_index=0, **overrides):
		receipt = order["receipts"][receipt_index]
		writer, stream = PdfWriter(), BytesIO()
		writer.add_blank_page(width=595, height=842)
		writer.write(stream)
		return record_supplier_invoice(order["name"], {"request_key": str(uuid4()), "receipt": receipt["name"], "bill_no": "HOME-BILL-" + str(uuid4())[:10], "bill_date": add_days(nowdate(), -1), "due_date": nowdate(), "items": [{"receipt_item": row.name, "expense_account": self.expense} for row in receipt["items"]], "proof": {"file_name": "supplier-bill.pdf", "content": base64.b64encode(stream.getvalue()).decode()}, **overrides})

	def test_full_order_advance_delivery_bill_and_final_payment(self):
		order = self.approved_order(100000)
		self.assertEqual(order["workflow_state"], "Approved")
		self.assertFalse(frappe.db.exists("GL Entry", {"voucher_no": order["name"]}))
		frappe.set_user(self.accounts)
		order = record_vendor_payment(order["name"], self.payment(50000))
		self.assertEqual(order["advance_paid"], 50000)
		advance = order["payments"][0]
		advance_account = frappe.db.get_value("Company", self.company, "default_advance_paid_account")
		self.assertEqual(advance.paid_to, advance_account)
		self.assertAlmostEqual(self.balance(advance_account, advance.name), 50000)
		frappe.set_user(self.requester)
		order = self.receipt(order)
		frappe.set_user(self.accounts)
		order = self.invoice(order)
		bill = order["invoices"][0]
		self.assertEqual(bill.total_advance, 50000)
		self.assertEqual(bill.outstanding_amount, 50000)
		self.assertEqual(str(bill.posting_date), add_days(nowdate(), -1))
		from volunteering.volunteering.budget_service import get_budget_commitment_breakdown
		breakdown = get_budget_commitment_breakdown(self.project)
		self.assertGreaterEqual(breakdown["posted_supplier_bills"], 100000)
		self.assertAlmostEqual(self.balance(self.expense, bill.name), 100000)
		order = record_vendor_payment(order["name"], self.payment(50000, invoice=bill.name))
		self.assertAlmostEqual(order["invoices"][0].outstanding_amount, 0)
		self.assertEqual(len(order["payments"]), 2)
		self.assertEqual(sum(payment.paid_amount for payment in order["payments"]), 100000)
		self.assertEqual(get_budget_commitment_breakdown(self.project)["total_committed"], breakdown["total_committed"])
		frappe.set_user(self.requester)
		self.assertTrue(get_purchase(order["name"])["attachments"])

	def balance(self, account, voucher):
		return sum(row.debit - row.credit for row in frappe.get_all("GL Entry", filters={"account": account, "voucher_no": voucher, "is_cancelled": 0}, fields=["debit", "credit"]))

	def test_ownership_membership_and_accounts_permissions(self):
		frappe.set_user(self.other)
		with self.assertRaises(frappe.PermissionError):
			save_purchase(self.payload())
		frappe.set_user(self.requester)
		order = save_purchase(self.payload())
		self.assertFalse(frappe.db.exists("DocShare", {"user": self.requester, "share_doctype": "Account"}))
		payable = frappe.get_cached_value("Company", self.company, "default_payable_account")
		self.assertFalse(frappe.has_permission("Account", "read", payable))
		with self.assertRaises(frappe.PermissionError):
			record_vendor_payment(order["name"], self.payment(100))
		with self.assertRaises(frappe.PermissionError):
			create_purchase_master("supplier", {})
		frappe.set_user(self.other)
		with self.assertRaises(frappe.PermissionError):
			get_purchase(order["name"])
		self.assertNotIn(order["name"], [row.name for row in get_purchase_workspace()["orders"]])
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			get_purchase_workspace()

	def test_retries_and_partial_deliveries_do_not_duplicate(self):
		frappe.set_user(self.requester)
		payload = self.payload()
		one = save_purchase(payload)
		two = save_purchase(payload)
		self.assertEqual(one["name"], two["name"])
		order = save_purchase(payload, one["name"], one["modified"], submit=1)
		frappe.set_user(self.manager)
		order = review_purchase(order["name"], "Approve", order["modified"])
		frappe.set_user(self.accounts)
		payment = self.payment(400)
		order = record_vendor_payment(order["name"], payment)
		order = record_vendor_payment(order["name"], payment)
		self.assertEqual(len(order["payments"]), 1)
		order = self.receipt(order, qty=4)
		self.assertEqual(order["items"][0]["received_qty"], 4)
		order = self.invoice(order)
		self.assertEqual(order["invoices"][0].grand_total, 400)
		self.assertEqual(order["invoices"][0].outstanding_amount, 0)
		order = self.receipt(order, qty=6)
		self.assertEqual(order["items"][0]["received_qty"], 10)
		self.assertEqual(len(order["receipts"]), 2)

	def test_reject_missing_proof_overpayment_and_overdelivery(self):
		order = self.approved_order()
		frappe.set_user(self.accounts)
		with self.assertRaises(frappe.ValidationError):
			record_vendor_payment(order["name"], self.payment(1001))
		with self.assertRaises(frappe.ValidationError):
			self.receipt(order, qty=11)
		order = self.receipt(order)
		with self.assertRaises(frappe.ValidationError):
			self.invoice(order, proof=None)

	def test_accounts_can_raise_order_for_a_project_without_membership(self):
		frappe.set_user(self.accounts)
		workspace = get_purchase_workspace("accounts")
		self.assertTrue(workspace["advance_setup"]["ready"])
		self.assertIn("Nos", workspace["uoms"])
		self.assertTrue(workspace["payment_accounts"])
		order = save_purchase(self.payload(), submit=1)
		self.assertEqual(order["workflow_state"], "Pending Approval")

	def test_stale_draft_and_unassigned_review_are_rejected(self):
		frappe.set_user(self.requester)
		payload = self.payload()
		order = save_purchase(payload)
		with self.assertRaises(frappe.TimestampMismatchError):
			save_purchase(payload, order["name"], modified="2000-01-01 00:00:00")
		with self.assertRaises(frappe.PermissionError):
			review_purchase(order["name"], "Approve", order["modified"])
		with self.assertRaises(frappe.PermissionError):
			configure_vendor_advances()

	def test_simple_stock_items_record_receipt_without_expensing_purchase(self):
		frappe.set_user("Administrator")
		item_name = "_Home Purchase Stock Test"
		if not frappe.db.exists("Item", item_name):
			frappe.get_doc({"doctype": "Item", "item_code": item_name, "item_name": "Stored kitchen plates", "is_stock_item": 1, "is_purchase_item": 1, "stock_uom": "Nos", "item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")}).insert()
		warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 0, "disabled": 0}, "name")
		frappe.set_user(self.requester)
		data = self.payload()
		data["items"][0].update({"item_code": item_name, "warehouse": warehouse})
		order = save_purchase(data, submit=1)
		frappe.set_user(self.manager)
		order = review_purchase(order["name"], "Approve", order["modified"])
		frappe.set_user(self.accounts)
		order = self.receipt(order)
		order = self.invoice(order)
		self.assertEqual(order["invoices"][0].outstanding_amount, 1000)
		if frappe.get_cached_value("Company", self.company, "enable_perpetual_inventory"):
			self.assertEqual(self.balance(self.expense, order["invoices"][0].name), 0)

	def test_payment_key_cannot_be_reused_for_another_order(self):
		first = self.approved_order()
		second = self.approved_order()
		frappe.set_user(self.accounts)
		payment = self.payment(100)
		record_vendor_payment(first["name"], payment)
		with self.assertRaises(frappe.ValidationError):
			record_vendor_payment(second["name"], payment)

	def test_review_escalates_to_new_assignee_without_a_broad_purchase_role(self):
		frappe.set_user(self.requester)
		order = save_purchase(self.payload(3000), submit=1)
		frappe.set_user("Administrator")
		department = frappe.db.get_value("Employee", {"user_id": self.manager}, "department")
		user = get_or_create_user("purchase-home-director@example.com", ["Employee", "Expense Approver"], "Rahul Director")
		director = get_or_create_employee(user, department, "Rahul")
		set_employee_grade(director, "Board of Directors")
		manager = frappe.db.get_value("Employee", {"user_id": self.manager}, "name")
		set_employee_grade(manager, "Manager", reports_to=director)
		frappe.set_user(self.manager)
		result = review_purchase(order["name"], "Escalate", order["modified"], "Amount above my current authority")
		self.assertTrue(result["redirect_to_list"])
		frappe.set_user(user)
		order = get_purchase(order["name"])
		self.assertEqual(order["pending_approver"], user)
		order = review_purchase(order["name"], "Approve", order["modified"])
		self.assertEqual(order["workflow_state"], "Approved")

	def test_cash_limit_is_enforced_even_without_a_cash_named_payment_mode(self):
		order = self.approved_order(3000)
		frappe.set_user("Administrator")
		frappe.db.set_single_value("Volunteering Accounting Settings", "cash_payment_limit", 2000)
		frappe.set_user(self.accounts)
		with self.assertRaisesRegex(frappe.ValidationError, "Cash payments cannot exceed"):
			record_vendor_payment(order["name"], self.payment(2500, paid_from=self.cash))

	def test_included_tax_breakup_is_optional_and_keeps_gross_cost_payable_and_advance(self):
		order = self.approved_order(1180)
		frappe.set_user(self.accounts)
		order = record_vendor_payment(order["name"], self.payment(500))
		order = self.receipt(order)
		ref = order["receipts"][0]["items"][0].name
		order = self.invoice(order, tax_breakup=[{"receipt_item": ref, "cgst": 90, "sgst": 90}])
		bill = order["invoices"][0]
		self.assertEqual(bill.grand_total, 1180)
		self.assertEqual(bill.outstanding_amount, 680)
		self.assertEqual(bill.total_advance, 500)
		self.assertAlmostEqual(self.balance(self.expense, bill.name), 1180)
		stored = frappe.parse_json(frappe.db.get_value("Purchase Invoice", bill.name, "home_purchase_tax_breakup"))
		self.assertEqual(stored["base_total"], 1000)
		self.assertEqual(stored["tax_total"], 180)
		self.assertEqual(stored["gross_total"], 1180)
		self.assertEqual(stored["recorded_by"], self.accounts)
		self.assertEqual(stored["items"][0]["cgst"], 90)
		self.assertEqual(bill["tax_breakup"], stored)
		invoice = frappe.get_doc("Purchase Invoice", bill.name)
		self.assertFalse(invoice.taxes)
		self.assertEqual(invoice.net_total, 1180)
		self.assertEqual(frappe.db.get_value("Purchase Order", order["name"], "grand_total"), 1180)
		frappe.set_user(self.requester)
		self.assertNotIn("tax_breakup", get_purchase(order["name"])["invoices"][0])
		self.assertNotIn("tax_templates", get_purchase_workspace())
		with self.assertRaises(frappe.PermissionError):
			record_supplier_invoice(order["name"], {})
		frappe.set_user(self.accounts)
		order = record_vendor_payment(order["name"], self.payment(680, invoice=bill.name))
		self.assertEqual(order["invoices"][0].outstanding_amount, 0)

	def test_bills_without_optional_tax_breakup_keep_the_entire_inclusive_cost(self):
		order = self.approved_order(1180)
		self.assertTrue(order["prices_include_tax"])
		frappe.set_user(self.accounts)
		order = self.invoice(self.receipt(order))
		bill = order["invoices"][0]
		self.assertIsNone(bill["tax_breakup"])
		self.assertFalse(frappe.db.get_value("Purchase Invoice", bill.name, "home_purchase_tax_breakup"))
		self.assertEqual(bill.grand_total, 1180)
		self.assertEqual(bill.outstanding_amount, 1180)
		self.assertEqual(self.balance(self.expense, bill.name), 1180)

	def test_invalid_tax_breakups_are_rejected_before_creating_any_bill(self):
		order = self.approved_order(1180)
		frappe.set_user(self.accounts)
		order = self.receipt(order)
		ref = order["receipts"][0]["items"][0].name
		invalid = [[], {}, [{"receipt_item": "another-delivery", "cgst": 90}],
			[{"receipt_item": ref, "cgst": -1}], [{"receipt_item": ref, "cgst": "NaN"}],
			[{"receipt_item": ref, "cgst": "Infinity"}], [{"receipt_item": ref, "cgst": 0.001}],
			[{"receipt_item": ref, "cgst": 1181}], [{"receipt_item": ref, "cgst": 700, "sgst": 700}],
			[{"receipt_item": ref, "cgst": 90, "igst": 90}], [{"receipt_item": ref, "input_tax_credit": 180}],
			[{"receipt_item": ref}, {"receipt_item": ref}],
		]
		for values in invalid:
			with self.subTest(values=values):
				with self.assertRaises(frappe.ValidationError):
					self.invoice(order, tax_breakup=values)
		self.assertFalse(frappe.db.exists("Purchase Invoice Item", {"purchase_order": order["name"]}))
		self.assertEqual(frappe.db.get_value("Purchase Order", order["name"], "per_billed"), 0)

	def test_home_orders_reject_template_injection_and_ignore_default_tax_templates(self):
		frappe.set_user("Administrator")
		tax_account = frappe.db.get_value("Account", {"company": self.company, "is_group": 0, "account_type": "Tax", "disabled": 0}, "name")
		template = frappe.get_doc({"doctype": "Purchase Taxes and Charges Template", "title": "Inclusive Home Test " + str(uuid4())[:8], "company": self.company, "is_default": 1,
			"taxes": [{"charge_type": "On Net Total", "account_head": tax_account, "description": "Test-only extra tax", "rate": 18, "category": "Total", "add_deduct_tax": "Add"}],
		}).insert()
		frappe.db.set_single_value("Accounts Settings", "add_taxes_from_taxes_and_charges_template", 1)
		frappe.set_user(self.requester)
		data = self.payload(1180)
		with self.assertRaises(frappe.PermissionError):
			save_purchase({**data, "taxes_and_charges": template.name})
		order = save_purchase(data, submit=1)
		self.assertEqual(order["grand_total"], 1180)
		self.assertEqual(order["tax_amount"], 0)
		frappe.set_user(self.manager)
		order = review_purchase(order["name"], "Approve", order["modified"])
		frappe.set_user(self.accounts)
		order = self.invoice(self.receipt(order))
		self.assertEqual(order["invoices"][0].grand_total, 1180)
		self.assertEqual(self.balance(self.expense, order["invoices"][0].name), 1180)

	def test_per_item_igst_and_other_tax_breakup_with_partial_delivery(self):
		frappe.set_user(self.requester)
		data = self.payload(1180)
		data["items"].append({"item_code": self.item, "qty": 2, "rate": 50})
		order = save_purchase(data, submit=1)
		frappe.set_user(self.manager)
		order = review_purchase(order["name"], "Approve", order["modified"])
		frappe.set_user(self.accounts)
		order = record_goods_received(order["name"], {"request_key": str(uuid4()), "posting_date": nowdate(), "items": [{"order_item": row["name"], "qty": row["qty"] / 2} for row in order["items"]]})
		receipt = order["receipts"][0]
		values = [{"receipt_item": row.name, **({"igst": 90} if row.amount == 590 else {"other_tax": 2.50})} for row in receipt["items"]]
		order = self.invoice(order, tax_breakup=values)
		stored = order["invoices"][0]["tax_breakup"]
		self.assertEqual(stored["gross_total"], 640)
		self.assertEqual(stored["tax_total"], 92.5)
		self.assertEqual(stored["base_total"], 547.5)
		self.assertEqual(self.balance(self.expense, order["invoices"][0].name), 640)

	def test_older_orders_keep_existing_erp_tax_rows_when_employee_edits_them(self):
		frappe.set_user(self.requester)
		data = self.payload(1000)
		order = save_purchase(data)
		frappe.set_user("Administrator")
		tax_account = frappe.db.get_value("Account", {"company": self.company, "is_group": 0, "account_type": "Tax", "disabled": 0}, "name")
		legacy = frappe.get_doc("Purchase Order", order["name"])
		legacy.append("taxes", {"charge_type": "On Net Total", "account_head": tax_account, "description": "Historical tax row", "rate": 18, "category": "Total", "add_deduct_tax": "Add"})
		legacy.save(ignore_permissions=True)
		frappe.set_user(self.requester)
		order = save_purchase(data, legacy.name, str(legacy.modified), submit=1)
		self.assertFalse(order["prices_include_tax"])
		self.assertEqual(order["grand_total"], 1180)
		self.assertEqual(order["tax_amount"], 180)
		frappe.set_user(self.manager)
		order = review_purchase(order["name"], "Approve", order["modified"])
		frappe.set_user(self.accounts)
		order = self.receipt(order)
		ref = order["receipts"][0]["items"][0].name
		with self.assertRaises(frappe.ValidationError):
			self.invoice(order, tax_breakup=[{"receipt_item": ref, "cgst": 90, "sgst": 90}])
		order = self.invoice(order)
		self.assertEqual(order["invoices"][0].grand_total, 1180)

	def test_mixed_accounts_and_approver_user_has_three_separate_purchase_workspaces(self):
		approved = self.approved_order(1000)
		frappe.set_user("Administrator")
		accounts_employee = frappe.db.get_value("Employee", {"user_id": self.accounts}, "name")
		requester_employee = frappe.db.get_value("Employee", {"user_id": self.requester}, "name")
		manager_employee = frappe.db.get_value("Employee", {"user_id": self.manager}, "name")
		set_employee_grade(accounts_employee, "Manager", reports_to=manager_employee)
		set_employee_grade(requester_employee, "Associate", reports_to=accounts_employee)
		frappe.set_user(self.requester)
		assigned = save_purchase(self.payload(900), submit=1)
		self.assertEqual(assigned["pending_approver"], self.accounts)
		frappe.set_user(self.accounts)
		own = save_purchase(self.payload(800))
		requests = get_purchase_workspace("requests")
		self.assertEqual([row.name for row in requests["orders"]], [own["name"]])
		self.assertFalse(requests["capabilities"]["accounts"])
		self.assertTrue(requests["capabilities"]["create"])
		self.assertFalse(requests["payment_accounts"])
		self.assertIsNone(requests["advance_setup"])
		approvals = get_purchase_workspace("approvals")
		self.assertEqual([row.name for row in approvals["orders"]], [assigned["name"]])
		self.assertFalse(approvals["capabilities"]["create"])
		self.assertFalse(approvals["capabilities"]["accounts"])
		self.assertTrue(get_purchase(assigned["name"], "approvals")["actions"]["review"])
		accounting = get_purchase_workspace("accounts")
		self.assertIn(approved["name"], [row.name for row in accounting["orders"]])
		self.assertNotIn(assigned["name"], [row.name for row in accounting["orders"]])
		self.assertNotIn(own["name"], [row.name for row in accounting["orders"]])
		self.assertTrue(accounting["capabilities"]["accounts"])
		self.assertFalse(accounting["capabilities"]["create"])
		self.assertTrue(get_purchase(approved["name"], "accounts")["actions"]["pay"])
		self.assertFalse(get_purchase(own["name"], "requests")["actions"]["pay"])
		for name, view in ((assigned["name"], "requests"), (own["name"], "approvals"), (own["name"], "accounts"), (assigned["name"], "accounts")):
			with self.subTest(name=name, view=view), self.assertRaises(frappe.PermissionError):
				get_purchase(name, view)

	def test_scoped_accounts_page_is_denied_to_employee_and_approval_page_empties_after_review(self):
		frappe.set_user(self.requester)
		pending = save_purchase(self.payload(1000), submit=1)
		with self.assertRaises(frappe.PermissionError):
			get_purchase_workspace("accounts")
		with self.assertRaises(frappe.PermissionError):
			get_purchase(pending["name"], "accounts")
		self.assertFalse(get_purchase_workspace("approvals")["orders"])
		with self.assertRaises(frappe.ValidationError):
			get_purchase_workspace("everyone")
		frappe.set_user(self.manager)
		self.assertIn(pending["name"], [row.name for row in get_purchase_workspace("approvals")["orders"]])
		self.assertNotIn(pending["name"], [row.name for row in get_purchase_workspace("requests")["orders"]])
		review_purchase(pending["name"], "Approve", pending["modified"])
		self.assertFalse(get_purchase_workspace("approvals")["orders"])
		with self.assertRaises(frappe.PermissionError):
			get_purchase(pending["name"], "approvals")
		frappe.set_user(self.accounts)
		self.assertIn(pending["name"], [row.name for row in get_purchase_workspace("accounts")["orders"]])
		frappe.set_user(self.requester)
		self.assertIn(pending["name"], [row.name for row in get_purchase_workspace("requests")["orders"]])
		self.assertFalse(get_purchase(pending["name"], "requests")["actions"]["pay"])

	def test_accounts_own_approved_purchase_has_no_processing_actions_in_personal_view(self):
		frappe.set_user(self.accounts)
		order = save_purchase(self.payload(1000), submit=1)
		frappe.set_user(order["pending_approver"])
		order = review_purchase(order["name"], "Approve", order["modified"])
		frappe.set_user(self.accounts)
		personal = get_purchase(order["name"], "requests")
		self.assertFalse(personal["actions"]["pay"])
		self.assertFalse(personal["actions"]["invoice"])
		self.assertFalse(personal["actions"]["review"])
		self.assertTrue(personal["actions"]["receive"])
		self.assertTrue(get_purchase(order["name"], "accounts")["actions"]["pay"])
