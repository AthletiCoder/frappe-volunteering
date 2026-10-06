# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import base64
from io import BytesIO
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.accounting_setup import (
	ensure_expense_claim_field_visibility,
	setup_accounting_custom_fields,
)
from volunteering.volunteering.approval_routing import get_document_approval_amount
from volunteering.volunteering.accounting_test_utils import (
	allow_project_expense_account,
	get_or_create_department,
	get_or_create_employee,
	get_or_create_expense_account,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	mute_accounting_test_emails,
	save_test_project,
)
from volunteering.volunteering.expense_claim_portal import (
	_attach_own_advance,
	_generated_invoice_claim_context,
	_normalise_expenses,
	get_expense_claim_form,
	get_my_expense_claim,
	get_my_expense_claims,
	get_project_accounts,
	resubmit_expense_claim,
	submit_expense_claim,
	submit_generated_invoice_expense_claim,
	submit_multi_invoice_expense_claim,
)
from volunteering.volunteering.expense_claim_workflow_portal import (
	get_expense_claim_work_item,
	get_expense_claim_work_queue,
)
from volunteering.volunteering.receipt_review import review_receipts


def _valid_pdf():
	from pypdf import PdfWriter

	buffer = BytesIO()
	writer = PdfWriter()
	writer.add_blank_page(width=72, height=72)
	writer.write(buffer)
	return buffer.getvalue()


class IntegrationTestExpenseClaimPortal(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._email_patcher = mute_accounting_test_emails()
		setup_accounting_custom_fields()
		ensure_expense_claim_field_visibility()
		cls.user = get_or_create_user(
			"expense-portal-employee@example.com", ["Employee", "Projects User"], "Portal Employee"
		)
		cls.department = get_or_create_department("Portal Operations")
		cls.employee = get_or_create_employee(cls.user, cls.department, "Portal Employee")
		cls.company = frappe.db.get_value("Employee", cls.employee, "company")
		cls.project = get_or_create_project_with_cost_center()
		cls.account = get_or_create_expense_account(cls.company)

	@classmethod
	def tearDownClass(cls):
		cls._email_patcher.close()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		project = frappe.get_doc("Project", self.project)
		project.project_setup_version = 1
		project.project_purpose = project.project_purpose or "Portal test project"
		project.project_owner = self.user
		project.operational_status = "Active"
		project.budget_status = "Active"
		project.is_archived = 0
		if self.user not in [row.user for row in project.project_participants]:
			project.append("project_participants", {"user": self.user, "access_level": "Basic"})
		save_test_project(project)
		allow_project_expense_account(self.project, self.account, label="Portal project costs")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Expense Claim", {"employee": self.employee})
		super().tearDown()

	def _payload(self, **overrides):
		payload = {
			"project": self.project,
			"reimbursement_source": "PERSONAL",
			"employee_advance": "",
			"is_emergency": False,
			"emergency_date": frappe.utils.nowdate(),
			"emergency_reason": "",
			"expenses": [
				{
					"expense_date": frappe.utils.nowdate(),
					"account": frappe.db.get_value(
						"Project Account Budget",
						{"parent": self.project, "expense_account": self.account},
						"budget_key",
					),
					"supplier_name": "Portal supplier",
					"invoice_number": "PORTAL-001",
					"description": "Portal test expense",
					"amount": 125,
					"receipt_filename": "receipt.png",
					"receipt_content": base64.b64encode(
						base64.b64decode(
							"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlVAAAAAASUVORK5CYII="
						)
					).decode(),
				}
			],
		}
		payload.update(overrides)
		return payload

	def test_defaults_and_accounts_disclose_only_safe_choices(self):
		frappe.set_user(self.user)
		defaults = get_expense_claim_form()
		self.assertEqual(defaults["employee"], self.employee)
		self.assertIn(self.project, [row["value"] for row in defaults["projects"]])
		accounts = get_project_accounts(self.project)
		key = frappe.db.get_value(
			"Project Account Budget", {"parent": self.project, "expense_account": self.account}, "budget_key"
		)
		self.assertIn(key, [row["value"] for row in accounts])
		self.assertNotIn(self.account, frappe.as_json(accounts))
		for account in accounts:
			self.assertNotIn("approved_amount", account)
			self.assertNotIn("balance", account)

	def test_submission_creates_private_item_receipt_and_enters_review(self):
		frappe.set_user(self.user)
		result = submit_expense_claim(self._payload())
		claim = frappe.get_doc("Expense Claim", result["name"])
		self.assertEqual(claim.employee, self.employee)
		self.assertEqual(claim.workflow_state, "Pending Receipt Review")
		self.assertEqual(claim.receipt_review_status, "Pending Review")
		self.assertEqual(claim.remark, "Portal test expense")
		self.assertEqual(claim.expenses[0].supplier_name, "Portal supplier")
		self.assertEqual(claim.expenses[0].supplier_invoice_number, "PORTAL-001")
		self.assertTrue(claim.expenses[0].receipt_attachment.startswith("/private/files/"))
		file_row = frappe.db.get_value(
			"File",
			{"attached_to_doctype": "Expense Claim", "attached_to_name": claim.name},
			["is_private", "file_url"],
			as_dict=True,
		)
		self.assertEqual(file_row.is_private, 1)
		self.assertEqual(file_row.file_url, claim.expenses[0].receipt_attachment)

	def test_multiple_invoices_create_separately_dated_linked_claims(self):
		frappe.set_user("Administrator")
		previous_year = "2025-2026"
		created_year = not frappe.db.exists("Fiscal Year", previous_year)
		if created_year:
			frappe.get_doc({
				"doctype": "Fiscal Year",
				"year": previous_year,
				"year_start_date": "2025-04-01",
				"year_end_date": "2026-03-31",
				"companies": [{"company": self.company}],
			}).insert()
		try:
			frappe.set_user(self.user)
			item = self._payload()["expenses"][0]
			invoice = lambda date, amount: {
				"invoice_date": date,
				"invoice_number": f"TEST-{date}",
				"supplier_name": "Portal supplier",
				"receipt_filename": "bill.pdf",
				"receipt_content": base64.b64encode(_valid_pdf()).decode(),
				"items": [
					{"account": item["account"], "description": "Billed item 1", "amount": amount},
					{"account": item["account"], "description": "Billed item 2", "amount": 25},
				],
			}
			result = submit_multi_invoice_expense_claim({
				"project": self.project,
				"reimbursement_source": "PERSONAL",
				"invoices": [invoice("2026-03-31", 100), invoice("2026-04-01", 200)],
			})
			self.assertEqual(result["total"], 350)
			claims = [frappe.get_doc("Expense Claim", row["name"]) for row in result["claims"]]
			self.assertEqual([str(row.posting_date) for row in claims], ["2026-03-31", "2026-04-01"])
			for claim, expected_year in zip(claims, ["2025-2026", "2026-2027"]):
				gl_row = claim.get_gl_dict({"account": self.account, "debit": 1})
				self.assertEqual(gl_row.posting_date, claim.posting_date)
				self.assertEqual(gl_row.fiscal_year, expected_year)
			self.assertEqual({row.expense_submission_id for row in claims}, {result["submission_id"]})
			for claim in claims:
				self.assertEqual(claim.workflow_state, "Pending Receipt Review")
				self.assertEqual(get_document_approval_amount(claim), 350)
				self.assertEqual(claim.expenses[0].receipt_attachment, claim.expenses[1].receipt_attachment)
				self.assertEqual(
					frappe.db.count("File", {"attached_to_doctype": "Expense Claim", "attached_to_name": claim.name}),
					1,
				)
		finally:
			frappe.set_user("Administrator")
			if created_year:
				frappe.db.delete("Expense Claim", {"employee": self.employee})
				frappe.delete_doc("Fiscal Year", previous_year)

	def test_single_claim_rejects_mixed_invoice_dates(self):
		frappe.set_user(self.user)
		payload = self._payload()
		payload["expenses"].append({**payload["expenses"][0], "expense_date": "2026-04-01"})
		with self.assertRaises(frappe.ValidationError):
			submit_expense_claim(payload)
		self.assertFalse(frappe.db.exists("Expense Claim", {"employee": self.employee}))

	def test_invalid_second_invoice_creates_no_partial_submission(self):
		frappe.set_user(self.user)
		item = self._payload()["expenses"][0]
		invoice = {
			"invoice_date": frappe.utils.nowdate(),
			"receipt_filename": "bill.pdf",
			"receipt_content": base64.b64encode(_valid_pdf()).decode(),
			"items": [{"account": item["account"], "description": "Billed item", "amount": 125}],
		}
		with self.assertRaises(frappe.ValidationError):
			submit_multi_invoice_expense_claim({
				"project": self.project,
				"reimbursement_source": "PERSONAL",
				"invoices": [invoice, {**invoice, "receipt_content": "invalid"}],
			})
		self.assertFalse(frappe.db.exists("Expense Claim", {"employee": self.employee}))

	def test_late_second_invoice_failure_rolls_back_first_claim(self):
		from volunteering.volunteering import expense_claim_portal

		frappe.set_user(self.user)
		item = self._payload()["expenses"][0]
		invoice = {
			"invoice_date": frappe.utils.nowdate(),
			"receipt_filename": "bill.pdf",
			"receipt_content": base64.b64encode(_valid_pdf()).decode(),
			"items": [{"account": item["account"], "description": "Billed item", "amount": 125}],
		}
		original = expense_claim_portal._submit_expense_claim_data
		calls = 0

		def fail_second(*args, **kwargs):
			nonlocal calls
			calls += 1
			if calls == 2:
				raise frappe.ValidationError("Second invoice failed after the first was saved")
			return original(*args, **kwargs)

		with patch.object(expense_claim_portal, "_submit_expense_claim_data", side_effect=fail_second):
			with self.assertRaisesRegex(frappe.ValidationError, "Second invoice failed"):
				submit_multi_invoice_expense_claim({
					"project": self.project,
					"reimbursement_source": "PERSONAL",
					"invoices": [invoice, invoice],
				})
		self.assertEqual(calls, 2)
		self.assertFalse(frappe.db.exists("Expense Claim", {"employee": self.employee}))

	@patch("volunteering.volunteering.invoice_generator.generate_invoice_documents")
	def test_signed_generated_invoice_is_privately_attached_and_submitted(self, generate):
		generate.return_value = {
			"invoice_number": "INV-2026-000321",
			"supplier_name": "Generated supplier",
			"grand_total": 125,
			"pdf": {
				"filename": "invoice-INV-2026-000321.pdf",
				"content_base64": base64.b64encode(_valid_pdf()).decode(),
			},
		}
		payload = self._payload()
		payload["expenses"][0].pop("receipt_filename")
		payload["expenses"][0].pop("receipt_content")
		frappe.set_user(self.user)
		invoice_payload = {
			"volunteer_signature_data": "data:image/png;base64,signed",
			"signature_context": _generated_invoice_claim_context(payload),
			"bank": {
				"account_name": "Generated supplier",
				"bank_name": "Supplier Bank",
				"account_number": "998877665544",
				"ifsc": "SUPP0123456",
			},
		}
		result = submit_generated_invoice_expense_claim(
			payload,
			invoice_payload,
		)
		claim = frappe.get_doc("Expense Claim", result["name"])
		self.assertEqual(result["generated_invoice_number"], "INV-2026-000321")
		self.assertEqual(claim.workflow_state, "Pending Receipt Review")
		self.assertEqual(claim.expenses[0].supplier_name, "Generated supplier")
		self.assertEqual(claim.expenses[0].supplier_invoice_number, "INV-2026-000321")
		self.assertTrue(claim.expenses[0].receipt_attachment.startswith("/private/files/"))
		generate.assert_called_once_with(invoice_payload, output_format="pdf")

	@patch("volunteering.volunteering.invoice_generator.generate_invoice_documents")
	def test_generated_invoice_requires_signature_and_matching_total(self, generate):
		payload = self._payload()
		payload["expenses"][0].pop("receipt_filename")
		payload["expenses"][0].pop("receipt_content")
		frappe.set_user(self.user)
		with self.assertRaisesRegex(frappe.ValidationError, "volunteer signature"):
			submit_generated_invoice_expense_claim(payload, {"volunteer_signature_data": ""})
		generate.assert_not_called()

		generate.return_value = {
			"invoice_number": "INV-2026-000322",
			"supplier_name": "Generated supplier",
			"grand_total": 124,
			"pdf": {
				"filename": "invoice.pdf",
				"content_base64": base64.b64encode(_valid_pdf()).decode(),
			},
		}
		with self.assertRaisesRegex(frappe.ValidationError, "must equal the expense amount"):
			submit_generated_invoice_expense_claim(
				payload,
				{
					"volunteer_signature_data": "data:image/png;base64,signed",
					"signature_context": _generated_invoice_claim_context(payload),
				},
			)
		self.assertFalse(frappe.db.exists("Expense Claim", {"employee": self.employee}))

	@patch("volunteering.volunteering.invoice_generator.generate_invoice_documents")
	def test_generated_invoice_rejects_claim_details_changed_after_signing(self, generate):
		payload = self._payload()
		invoice = {
			"volunteer_signature_data": "data:image/png;base64,signed",
			"signature_context": _generated_invoice_claim_context(payload),
		}
		payload["expenses"][0]["description"] = "Changed purpose after signing"
		frappe.set_user(self.user)
		with self.assertRaisesRegex(frappe.ValidationError, "changed after signing"):
			submit_generated_invoice_expense_claim(payload, invoice)
		generate.assert_not_called()

	@patch("volunteering.volunteering.invoice_generator.generate_invoice_documents")
	def test_generated_invoice_date_must_match_claim_bill_date(self, generate):
		payload = self._payload()
		invoice = {
			"invoice_date": "2026-04-01",
			"volunteer_signature_data": "data:image/png;base64,signed",
			"signature_context": _generated_invoice_claim_context(payload),
		}
		frappe.set_user(self.user)
		with self.assertRaisesRegex(frappe.ValidationError, "must match the bill date"):
			submit_generated_invoice_expense_claim(payload, invoice)
		generate.assert_not_called()

	def test_employee_can_correct_and_resubmit_from_home(self):
		frappe.set_user(self.user)
		result = submit_expense_claim(self._payload())
		frappe.set_user("Administrator")
		review_receipts(result["name"], "request_correction", "Clarify the supplier name.")

		frappe.set_user(self.user)
		detail = get_my_expense_claim(result["name"])
		self.assertTrue(detail["can_correct"])
		item = detail["expenses"][0]
		item["supplier_name"] = "Corrected supplier"
		item.pop("category")
		item.pop("sanctioned_amount")
		item.pop("receipt_attachment")
		corrected = resubmit_expense_claim(
			result["name"],
			{"expenses": [item], "correction_note": "Supplier name corrected."},
		)
		self.assertEqual(corrected["workflow_state"], "Pending Receipt Review")
		claim = frappe.get_doc("Expense Claim", result["name"])
		self.assertEqual(claim.expenses[0].supplier_name, "Corrected supplier")
		self.assertEqual(claim.receipt_review_status, "Pending Review")

	def test_employee_history_lists_and_opens_only_their_claim(self):
		frappe.set_user(self.user)
		result = submit_expense_claim(self._payload())
		workspace = get_my_expense_claims()
		row = next(item for item in workspace["claims"] if item["name"] == result["name"])
		self.assertEqual(row["stage"], "Receipt review")
		self.assertEqual(row["project"], self.project)
		self.assertEqual(row["claimed_amount"], 125)
		self.assertGreaterEqual(workspace["counts"]["Receipt review"], 1)

		detail = get_my_expense_claim(result["name"])
		self.assertEqual(detail["name"], result["name"])
		self.assertEqual(detail["source"], "Paid personally")
		self.assertEqual(detail["expenses"][0]["category"], "Portal project costs")
		self.assertTrue(detail["expenses"][0]["receipt_attachment"].startswith("/private/files/"))
		self.assertEqual(detail["timeline"][0]["label"], "Claim created")

	def test_legacy_project_claim_is_hidden_from_home_history_and_review(self):
		frappe.set_user(self.user)
		name = submit_expense_claim(self._payload())["name"]
		frappe.set_user("Administrator")
		frappe.db.set_value("Project", self.project, "project_setup_version", 0)

		frappe.set_user(self.user)
		self.assertNotIn(name, [row["name"] for row in get_my_expense_claims()["claims"]])
		with self.assertRaises(frappe.PermissionError):
			get_my_expense_claim(name)

		frappe.set_user("Administrator")
		self.assertNotIn(
			name,
			[row["name"] for row in get_expense_claim_work_queue()["queues"]["receipt_review"]],
		)
		with self.assertRaises(frappe.PermissionError):
			get_expense_claim_work_item(name)

	def test_each_expense_requires_its_own_receipt(self):
		frappe.set_user(self.user)
		payload = self._payload()
		second = dict(payload["expenses"][0], receipt_content="", receipt_filename="")
		payload["expenses"].append(second)
		with self.assertRaises(frappe.ValidationError):
			submit_expense_claim(payload)
		self.assertFalse(frappe.db.exists("Expense Claim", {"employee": self.employee}))

	def test_employee_cannot_send_internal_accounting_fields(self):
		frappe.set_user(self.user)
		with self.assertRaises(frappe.ValidationError):
			submit_expense_claim(self._payload(payable_account=self.account))

	def test_forged_project_account_is_rejected(self):
		frappe.set_user(self.user)
		allowed = {row["value"] for row in get_project_accounts(self.project)}
		frappe.set_user("Administrator")
		other = frappe.db.get_value(
			"Account",
			{
				"company": self.company,
				"root_type": "Expense",
				"is_group": 0,
				"disabled": 0,
				"name": ["not in", list(allowed)],
			},
			"name",
		)
		if not other:
			self.skipTest("The test company has only one leaf Expense Account")
		payload = self._payload()
		payload["expenses"][0]["account"] = other
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			submit_expense_claim(payload)

	def test_project_membership_is_checked_server_side(self):
		try:
			frappe.set_user("Administrator")
			frappe.db.delete("Project Participant", {"parent": self.project, "user": self.user})
			frappe.set_user(self.user)
			with self.assertRaises(frappe.PermissionError):
				submit_expense_claim(self._payload())
		finally:
			frappe.set_user("Administrator")
			project = frappe.get_doc("Project", self.project)
			if self.user not in [row.user for row in project.project_participants]:
				project.append("project_participants", {"user": self.user, "access_level": "Basic"})
			save_test_project(project)


class UnitTestExpenseClaimPortal(UnitTestCase):
	def test_non_finite_amount_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			_normalise_expenses([{"account": "ACCOUNT", "amount": "nan"}], {"ACCOUNT"})

	def test_fake_pdf_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			_normalise_expenses(
				[
					{
						"account": "ACCOUNT",
						"amount": 10,
						"receipt_filename": "receipt.pdf",
						"receipt_content": base64.b64encode(b"not a PDF").decode(),
					}
				],
				{"ACCOUNT"},
			)

	@patch("hrms.hr.doctype.expense_claim.expense_claim.get_expense_claim_advances")
	@patch("volunteering.volunteering.expense_claim_portal.frappe.get_doc")
	@patch("volunteering.volunteering.expense_claim_portal.is_home_advance", return_value=True)
	def test_paid_own_advance_allocates_only_up_to_claim_total(self, _home, get_doc, get_advances):
		get_doc.return_value = frappe._dict(
			employee="EMPLOYEE",
			company="COMPANY",
			docstatus=1,
			paid_amount=1000,
			claimed_amount=100,
			return_amount=50,
			currency="INR",
		)
		# get_doc is mocked only to resolve the advance; use a real empty claim.
		from hrms.hr.doctype.expense_claim.expense_claim import ExpenseClaim

		doc = ExpenseClaim({"doctype": "Expense Claim", "company": "COMPANY", "currency": "INR"})
		get_advances.side_effect = lambda claim, advance: claim.append(
			"advances", {"unclaimed_amount": 900, "return_amount": 50}
		)
		_attach_own_advance(doc, "ADVANCE", "EMPLOYEE", 125)
		self.assertEqual(doc.advances[0].allocated_amount, 125)

	@patch("volunteering.volunteering.expense_claim_portal.frappe.get_doc")
	@patch("volunteering.volunteering.expense_claim_portal.is_home_advance", return_value=True)
	def test_another_employees_advance_is_rejected(self, _home, get_doc):
		get_doc.return_value = frappe._dict(employee="OTHER", company="COMPANY")
		with self.assertRaises(frappe.PermissionError):
			_attach_own_advance(frappe._dict(company="COMPANY"), "ADVANCE", "EMPLOYEE", 125)

	@patch("volunteering.volunteering.expense_claim_portal.frappe.get_doc")
	@patch("volunteering.volunteering.expense_claim_portal.is_home_advance", return_value=True)
	def test_unpaid_advance_is_rejected(self, _home, get_doc):
		get_doc.return_value = frappe._dict(
			employee="EMPLOYEE",
			company="COMPANY",
			docstatus=1,
			paid_amount=0,
		)
		with self.assertRaises(frappe.ValidationError):
			_attach_own_advance(frappe._dict(company="COMPANY"), "ADVANCE", "EMPLOYEE", 125)
