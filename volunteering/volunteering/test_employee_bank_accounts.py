import base64
from io import BytesIO
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering import employee_bank_accounts as banking
from volunteering.volunteering import invoice_generator as invoices
from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department,
	get_or_create_employee,
	get_or_create_payable_account,
	get_or_create_user,
	mute_accounting_test_emails,
)
from volunteering.volunteering.home_service import _bank_review_actions
from volunteering.volunteering.test_invoice_generator import _payload


def details(number="123456789012"):
	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=300, height=300)
	proof = BytesIO()
	writer.write(proof)
	return {
		"account_holder_name": "Test Employee",
		"bank_name": "Test Reimbursement Bank",
		"branch": "Test Branch",
		"account_type": "Savings",
		"account_number": number,
		"account_number_confirmation": number,
		"ifsc": "TEST0123456",
		"swift": "TESTINBB",
		"ownership_confirmed": True,
		"proof_filename": "proof.pdf",
		"proof_content": base64.b64encode(proof.getvalue()).decode(),
	}


class UnitTestEmployeeBankDetails(UnitTestCase):
	def test_confirmation_ifsc_and_ownership_are_required(self):
		for overrides in (
			{"account_number_confirmation": "999999"},
			{"ifsc": "INVALID"},
			{"ownership_confirmed": False},
			{"account_type": "Unrecognised"},
			{"account_number": "1" * 31, "account_number_confirmation": "1" * 31},
		):
			with self.assertRaises(frappe.ValidationError):
				banking._normalise_details({**details(), **overrides})

	def test_proof_must_match_allowed_file_type(self):
		for overrides in (
			{"proof_filename": "proof.html"},
			{"proof_content": "not-base64"},
			{"proof_filename": "proof.png"},
			{"proof_filename": ""},
		):
			with self.assertRaises(frappe.ValidationError):
				banking._proof({**details(), **overrides})

	def test_only_accounts_manager_gets_home_review_action(self):
		for roles, expected in (
			(["Accounts User"], []),
			(["System Manager"], []),
			(["Accounts Manager"], ["bank_account", "project_account_mapping"]),
		):
			with patch("frappe.get_roles", return_value=roles):
				self.assertEqual(
					[action["id"] for action in _bank_review_actions("test@example.com")], expected
				)


class IntegrationTestEmployeeBankAccounts(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.emails = mute_accounting_test_emails()
		frappe.set_user("Administrator")
		cls.employee_user = get_or_create_user("bank-employee@example.com", ["Employee"])
		cls.other_user = get_or_create_user("bank-other@example.com", ["Employee"])
		cls.manager = get_or_create_user("bank-manager@example.com", ["Employee", "Accounts Manager"])
		cls.operator = get_or_create_user("bank-operator@example.com", ["Employee", "Accounts User"])
		cls.projects = get_or_create_user("bank-projects@example.com", ["Employee", "Projects Manager"])
		cls.system = get_or_create_user("bank-system@example.com", ["Employee", "System Manager"])
		department = get_or_create_department("Bank Workflow Test")
		with patch("volunteering.volunteering.leave_setup.assign_leave_policy_to_employee"):
			cls.employee = get_or_create_employee(cls.employee_user, department)
			cls.other_employee = get_or_create_employee(cls.other_user, department)
			for user in (cls.manager, cls.operator, cls.projects, cls.system):
				get_or_create_employee(user, department)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		cls.emails.close()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("employee_bank_test")
		self.addCleanup(self.rollback_test)
		frappe.set_user(self.employee_user)
		self.request = banking.submit_bank_account_request(details())

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def rollback_test(self):
		frappe.db.rollback(save_point="employee_bank_test")
		frappe.db.value_cache.clear()

	def approve(self, request=None):
		request = request or self.request
		frappe.set_user(self.manager)
		return banking.review_bank_account_request(request["name"], "approve", request["modified"])

	def test_pending_is_bound_to_employee_masked_encrypted_and_not_published(self):
		self.assertEqual(self.request["employee"], self.employee)
		self.assertEqual(self.request["submitted_by"], self.employee_user)
		self.assertNotIn("account_number", self.request)
		self.assertEqual(self.request["account_number_masked"], "••••••9012")
		self.assertFalse(self.request["bank_account"])
		self.assertIsNone(banking.get_approved_bank_details(self.employee))
		stored = frappe.db.get_value(banking.REQUEST_DOCTYPE, self.request["name"], "account_number")
		self.assertNotEqual(stored, details()["account_number"])
		self.assertEqual(
			banking._account_number(frappe.get_doc(banking.REQUEST_DOCTYPE, self.request["name"])),
			details()["account_number"],
		)
		workspace = banking.get_bank_account_workspace()
		self.assertFalse(workspace["can_review"])
		self.assertEqual(workspace["pending_requests"], [])
		self.assertNotIn("account_number", workspace["requests"][0])

	def test_duplicate_pending_request_is_blocked(self):
		with self.assertRaises(frappe.ValidationError):
			banking.submit_bank_account_request(details("987654321012"))

	def test_non_accounts_manager_roles_cannot_decide_or_see_other_proof(self):
		file = frappe.get_doc(
			"File", {"file_url": self.request["proof_url"], "attached_to_name": self.request["name"]}
		)
		for user in (self.employee_user, self.other_user, self.operator, self.projects, self.system):
			frappe.set_user(user)
			for action in ("approve", "return", "reject"):
				with self.assertRaises(frappe.PermissionError):
					banking.review_bank_account_request(
						self.request["name"], action, self.request["modified"], comments="Reviewed"
					)
			if user != self.employee_user:
				self.assertFalse(file.has_permission("read"))
				self.assertFalse(file.is_downloadable())
				with self.assertRaises(frappe.PermissionError):
					file.get_content()
		frappe.set_user(self.employee_user)
		self.assertTrue(file.is_downloadable())
		frappe.set_user(self.manager)
		self.assertTrue(file.is_downloadable())
		self.assertEqual(
			banking.get_bank_account_workspace()["pending_requests"][0]["account_number"],
			details()["account_number"],
		)

	def test_approval_publishes_employee_bank_and_preserves_payroll(self):
		before = frappe.db.get_value(
			"Employee", self.employee, ["bank_name", "bank_ac_no", "ifsc_code"], as_dict=True
		)
		approved = self.approve()
		self.assertEqual(approved["request_status"], "Approved")
		self.assertEqual(approved["reviewed_by"], self.manager)
		self.assertTrue(approved["reviewed_on"])
		bank = frappe.get_doc("Bank Account", approved["bank_account"])
		self.assertEqual(bank.party_type, "Employee")
		self.assertEqual(bank.party, self.employee)
		self.assertTrue(bank.is_default)
		self.assertFalse(bank.disabled)
		self.assertEqual(bank.bank_account_no, details()["account_number"])
		self.assertEqual(
			before,
			frappe.db.get_value(
				"Employee", self.employee, ["bank_name", "bank_ac_no", "ifsc_code"], as_dict=True
			),
		)
		self.assertEqual(banking.get_approved_bank_details(self.employee)["account_name"], "Test Employee")

	def test_pending_replacement_preserves_active_account_then_supersedes(self):
		old = self.approve()
		frappe.set_user(self.employee_user)
		pending = banking.submit_bank_account_request(details("987654329012"))
		self.assertEqual(
			banking.get_approved_bank_details(self.employee)["account_number"], details()["account_number"]
		)
		new = self.approve(pending)
		self.assertNotEqual(new["bank_account"], old["bank_account"])
		self.assertEqual(
			frappe.db.get_value(banking.REQUEST_DOCTYPE, old["name"], "request_status"), "Superseded"
		)
		old_bank = frappe.get_doc("Bank Account", old["bank_account"])
		self.assertTrue(old_bank.disabled)
		self.assertFalse(old_bank.is_default)
		self.assertEqual(old_bank.bank_account_no, details()["account_number"])
		self.assertEqual(banking.get_approved_bank_details(self.employee)["account_number"], "987654329012")

	def test_return_reject_comments_and_resubmission_retain_history(self):
		frappe.set_user(self.manager)
		with self.assertRaises(frappe.ValidationError):
			banking.review_bank_account_request(self.request["name"], "return", self.request["modified"])
		returned = banking.review_bank_account_request(
			self.request["name"], "return", self.request["modified"], "Proof is unreadable"
		)
		self.assertEqual(returned["request_status"], "Returned")
		frappe.set_user(self.employee_user)
		new = banking.submit_bank_account_request(details("987654321234"))
		frappe.set_user(self.manager)
		rejected = banking.review_bank_account_request(
			new["name"], "reject", new["modified"], "Holder does not match"
		)
		self.assertEqual(rejected["request_status"], "Rejected")
		frappe.set_user(self.employee_user)
		self.assertEqual(
			{r["request_status"] for r in banking.get_bank_account_workspace()["requests"]},
			{"Returned", "Rejected"},
		)
		self.assertIsNone(banking.get_approved_bank_details(self.employee))

	def test_stale_and_repeat_decisions_cannot_publish_twice(self):
		frappe.set_user(self.manager)
		with self.assertRaises(frappe.TimestampMismatchError):
			banking.review_bank_account_request(self.request["name"], "approve", "2000-01-01")
		approved = self.approve()
		with self.assertRaises(frappe.ValidationError):
			banking.review_bank_account_request(approved["name"], "approve", approved["modified"])

	def test_direct_request_and_proof_mutations_and_sharing_are_blocked(self):
		frappe.set_user(self.manager)
		doc = frappe.get_doc(banking.REQUEST_DOCTYPE, self.request["name"])
		doc.request_status = "Approved"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(doc.doctype, doc.name, ignore_permissions=True)
		file = frappe.get_doc("File", {"file_url": self.request["proof_url"], "attached_to_name": doc.name})
		file.attached_to_doctype = None
		file.attached_to_name = None
		with self.assertRaises(frappe.PermissionError):
			file.save(ignore_permissions=True)
		for doctype, name in ((doc.doctype, doc.name), ("File", file.name)):
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "DocShare",
						"share_doctype": doctype,
						"share_name": name,
						"user": self.other_user,
						"read": 1,
					}
				).insert(ignore_permissions=True)

	def test_bank_destination_cannot_be_changed_directly_even_by_manager(self):
		approved = self.approve()
		for overrides in ({"bank_account_no": "999999999999"}, {"party_type": "Supplier", "party": None}):
			bank = frappe.get_doc("Bank Account", approved["bank_account"])
			bank.update(overrides)
			with self.assertRaises(frappe.PermissionError):
				bank.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Bank Account", approved["bank_account"], ignore_permissions=True)

	def test_invoice_requires_approval_and_defaults_are_masked(self):
		with self.assertRaises(frappe.ValidationError):
			invoices.generate_invoice_documents(_payload())
		self.approve()
		frappe.set_user(self.employee_user)
		defaults = invoices.get_invoice_generator_defaults()
		self.assertTrue(defaults["has_approved_bank"])
		self.assertEqual(defaults["remittance_bank"]["account_number"], "••••••9012")
		self.assertNotIn(details()["account_number"], str(defaults))

	def test_pdf_and_word_ignore_forged_remittance_and_use_approved_record(self):
		from docx import Document

		self.approve()
		frappe.set_user(self.employee_user)
		payload = _payload("NON_GST")
		payload["bank"] = {"account_number": "999999999999", "bank_name": "Forged Bank"}
		with patch.object(
			invoices, "_build_pdf", side_effect=lambda data: invoices._render_pdf_html(data).encode()
		):
			generated = invoices.generate_invoice_documents(payload)
		html = base64.b64decode(generated["pdf"]["content_base64"]).decode()
		word = Document(BytesIO(base64.b64decode(generated["docx"]["content_base64"])))
		text = "\n".join(cell.text for table in word.tables for row in table.rows for cell in row.cells)
		for content in (html, text):
			self.assertIn(details()["account_number"], content)
			self.assertIn("Test Reimbursement Bank", content)
			self.assertIn("Remittance Details", content)
			self.assertNotIn("999999999999", content)
			self.assertNotIn("Forged Bank", content)

	def payment(self, destination=None):
		return frappe._dict(
			payment_type="Pay",
			party_type="Employee",
			party=self.employee,
			paid_from="Test Bank Ledger",
			party_bank_account=destination,
		)

	def test_bank_payment_requires_approval_cash_remains_unchanged(self):
		with patch("frappe.db.get_value", return_value="Bank"):
			with self.assertRaises(frappe.ValidationError):
				banking.validate_employee_payment_bank(self.payment())
		cash = self.payment()
		with patch("frappe.db.get_value", return_value="Cash"):
			banking.validate_employee_payment_bank(cash)
		self.assertIsNone(cash.party_bank_account)

	def test_bank_payment_autofills_current_and_blocks_stale_destination(self):
		old = self.approve()
		real_get = frappe.db.get_value

		def value(doctype, *args, **kwargs):
			return "Bank" if doctype == "Account" else real_get(doctype, *args, **kwargs)

		with patch("frappe.db.get_value", side_effect=value):
			payment = self.payment()
			banking.validate_employee_payment_bank(payment)
			self.assertEqual(payment.party_bank_account, old["bank_account"])
			frappe.set_user(self.employee_user)
			pending = banking.submit_bank_account_request(details("987654321012"))
			new = self.approve(pending)
			with self.assertRaises(frappe.ValidationError):
				banking.validate_employee_payment_bank(payment)
			current = self.payment()
			banking.validate_employee_payment_bank(current)
			self.assertEqual(current.party_bank_account, new["bank_account"])

	def test_payment_entry_save_hook_requires_and_sets_approved_bank(self):
		from frappe.utils import nowdate

		frappe.set_user("Administrator")
		company = frappe.db.get_value("Employee", self.employee, "company")
		parent = frappe.db.get_value(
			"Account", {"company": company, "root_type": "Asset", "is_group": 1}, "name"
		)
		ledger = (
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "_Test Bank Approval Ledger " + frappe.generate_hash(length=6),
					"company": company,
					"parent_account": parent,
					"account_type": "Bank",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		currency = frappe.db.get_value("Company", company, "default_currency")

		def payment():
			return frappe.get_doc(
				{
					"doctype": "Payment Entry",
					"payment_type": "Pay",
					"company": company,
					"posting_date": nowdate(),
					"party_type": "Employee",
					"party": self.employee,
					"paid_from": ledger,
					"paid_to": get_or_create_payable_account(company),
					"paid_from_account_currency": currency,
					"paid_to_account_currency": currency,
					"source_exchange_rate": 1,
					"target_exchange_rate": 1,
					"paid_amount": 1,
					"received_amount": 1,
					"reference_no": "LOCAL-TEST",
					"reference_date": nowdate(),
				}
			)

		with self.assertRaisesRegex(frappe.ValidationError, "approve this employee"):
			payment().insert(ignore_permissions=True)
		approved = self.approve()
		doc = payment().insert(ignore_permissions=True)
		self.assertEqual(doc.party_bank_account, approved["bank_account"])
		frappe.set_user(self.employee_user)
		pending = banking.submit_bank_account_request(details("987654321012"))
		self.approve(pending)
		# Real submit dispatch must recheck a draft saved before a replacement.
		with self.assertRaisesRegex(frappe.ValidationError, "currently approved"):
			doc.run_method("before_submit")

	def test_tampered_record_is_not_used_for_documents_or_payments(self):
		approved = self.approve()
		frappe.db.set_value("Bank Account", approved["bank_account"], "bank_account_no", "999999999999")
		with self.assertRaises(frappe.ValidationError):
			banking.get_approved_bank_details(self.employee)

	def test_guest_and_inactive_employee_cannot_submit(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			banking.get_bank_account_workspace()
		frappe.set_user(self.other_user)
		frappe.db.set_value("Employee", self.other_employee, "status", "Inactive")
		with self.assertRaises(frappe.PermissionError):
			banking.submit_bank_account_request(details())
		with self.assertRaises(frappe.PermissionError):
			invoices.get_invoice_generator_defaults()
