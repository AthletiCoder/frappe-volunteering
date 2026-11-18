"""Accounts-only donation receipt and accounting tests."""

import base64
import os
from io import BytesIO
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.accounting_test_utils import get_or_create_user
from volunteering.volunteering.doctype.donation.donation import manual_donation_write
from volunteering.volunteering.donation_portal import (
	_amount,
	_receipt_pdf,
	_validate_account,
	bind_donation_donor_signature,
	get_donation_list,
	get_donation_workspace,
	issue_donation_receipt,
	register_donation,
	save_donation_receipt_settings,
	save_donation_signatory,
	update_donation_donor,
)


def _drawn_signature():
	from PIL import Image, ImageDraw

	image = Image.new("RGB", (320, 120), "white")
	ImageDraw.Draw(image).line([(20, 80), (95, 25), (180, 75), (300, 25)], fill="black", width=5)
	buffer = BytesIO()
	image.save(buffer, "PNG")
	return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


class UnitTestDonationPortal(UnitTestCase):
	def test_amount_validation(self):
		self.assertEqual(str(_amount("30000")), "30000.00")
		for value in ("0", "-5", "not-a-number"):
			with self.assertRaises(frappe.ValidationError):
				_amount(value)


class IntegrationTestDonationPortal(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.manager = get_or_create_user("donation-portal-manager@example.com", ["Accounts Manager"])
		cls.employee = get_or_create_user("donation-portal-employee@example.com", ["Employee"])
		company = "Sevamrita Foundation"
		cls.bank = frappe.db.get_value("Account", {"company": company, "account_name": "SF Axis Bank", "is_group": 0, "disabled": 0}, "name") or frappe.db.get_value("Account", {"company": company, "account_type": "Bank", "is_group": 0, "disabled": 0}, "name")
		cls.cash = frappe.db.get_value("Account", {"company": company, "account_type": "Cash", "is_group": 0, "disabled": 0}, "name")
		cls.income = frappe.db.get_value("Account", {"company": company, "account_name": "General Donations", "is_group": 0}, "name") or frappe.db.get_value("Account", {"company": company, "account_name": "Donation Income", "is_group": 0}, "name")

	def setUp(self):
		super().setUp()
		frappe.set_user(self.manager)
		save_donation_receipt_settings({
			"organisation_name": "Sevamrita Foundation", "registered_address": "301, Plot No 6, Kandi, Telangana 502285",
			"contact_email": "info@sevamrita.org", "cin": "U88900TS2024NPL190139",
			"organisation_pan": "ABOCS4775Q", "eighty_g_number": "ABOCS4775QF20251",
			"eighty_g_valid_until": frappe.utils.add_years(frappe.utils.nowdate(), 1),
		})
		self.signatory = "Receipt Test Signatory " + frappe.generate_hash(length=6)
		save_donation_signatory(self.signatory, "Treasurer", _drawn_signature())

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _details(self, **overrides):
		data = {
			"request_key": frappe.generate_hash(length=20),
			"donor_name": "Tejas Test " + frappe.generate_hash(length=6),
			"donor_type": "Individual", "address": "Pune, Maharashtra 411045",
			"pan": "BXVPP" + str(int(frappe.generate_hash(length=6), 16) % 10000).zfill(4) + "K", "mobile_number": "9876543210", "email": "",
			"amount": "30000", "received_on": frappe.utils.nowdate(),
			"donation_purpose": "General", "payment_method": "Online",
			"payment_reference": "IMPS-TEST-123", "received_into_account": self.bank,
			"donation_account": self.income, "receipt_signatory": self.signatory,
			"want_80g": 1,
		}
		data.update(overrides)
		return data

	def test_only_accounts_manager_can_use_home_donations(self):
		frappe.set_user(self.employee)
		with self.assertRaises(frappe.PermissionError):
			get_donation_workspace()
		with self.assertRaises(frappe.PermissionError):
			register_donation(self._details())
		with self.assertRaises(frappe.PermissionError):
			get_donation_list()
		with self.assertRaises(frappe.PermissionError):
			issue_donation_receipt("example", self.signatory)

	def test_record_post_receipt_without_phone_or_duplicate_posting(self):
		payload = self._details(mobile_number="")
		with patch("volunteering.volunteering.donation_portal._receipt_pdf", return_value=b"%PDF-1.4\n%%EOF"), patch(
			"frappe.utils.file_manager.save_file", return_value=frappe._dict(file_url="/private/files/test-donation-receipt.pdf")
		):
			first = register_donation(payload)
			again = register_donation(payload)
		self.assertEqual(first, again)
		donation = frappe.get_doc("Donation", first["name"])
		self.assertEqual(donation.donor_type, "Individual")
		self.assertFalse(donation.mobile_number)
		self.assertEqual(donation.receipt_file, "/private/files/test-donation-receipt.pdf")
		self.assertTrue(donation.donor)
		self.assertEqual(frappe.db.count("Donation Donor", {"name": donation.donor}), 1)
		journal = frappe.get_doc("Journal Entry", donation.journal_entry)
		self.assertEqual(journal.docstatus, 1)
		self.assertEqual(len(journal.accounts), 2)
		self.assertEqual({r.account for r in journal.accounts}, {self.bank, self.income})
		self.assertEqual(sum(r.debit_in_account_currency for r in journal.accounts), 30000)
		self.assertEqual(sum(r.credit_in_account_currency for r in journal.accounts), 30000)
		self.assertTrue(donation.receipt_number.startswith("RE-"))

	def test_post_without_receipt_setup_and_issue_later_without_posting_again(self):
		payload = self._details(mobile_number="", receipt_signatory="", want_80g=0, donation_purpose="")
		with patch("volunteering.volunteering.donation_portal._settings", side_effect=AssertionError("Receipt setup is independent")):
			recorded = register_donation(payload)
			self.assertEqual(register_donation(payload), recorded)
		pending = frappe.get_doc("Donation", recorded["name"])
		self.assertFalse(pending.receipt_number)
		self.assertFalse(pending.receipt_date)
		self.assertFalse(pending.receipt_signatory)
		self.assertFalse(pending.receipt_file)
		self.assertEqual(pending.donation_purpose, "General")
		self.assertEqual(pending.donation_account, self.income)
		self.assertEqual(frappe.db.get_value("Journal Entry", pending.journal_entry, "docstatus"), 1)
		self.assertIn(pending.name, {row.name for row in get_donation_list("pending")["rows"]})
		with self.assertRaisesRegex(frappe.ValidationError, "Authorised signatory is required"):
			issue_donation_receipt(pending.name, "")
		with patch("volunteering.volunteering.donation_portal._receipt_pdf", return_value=b"%PDF-1.4\n%%EOF") as pdf, patch(
			"frappe.utils.file_manager.save_file", return_value=frappe._dict(file_url="/private/files/late-donation-receipt.pdf")
		) as save:
			issued = issue_donation_receipt(pending.name, self.signatory, want_80g=1)
			self.assertEqual(issue_donation_receipt(pending.name, self.signatory), issued)
			pdf.assert_called_once()
			save.assert_called_once()
			self.assertEqual(save.call_args.kwargs["is_private"], 1)
		pending.reload()
		self.assertEqual(pending.receipt_signatory, self.signatory)
		self.assertEqual(str(pending.receipt_date), frappe.utils.nowdate())
		self.assertEqual(pending.want_80g, 1)
		self.assertEqual(pending.journal_entry, recorded["journal_entry"])
		self.assertEqual(frappe.db.count("Journal Entry", {"user_remark": ["like", f"%{pending.name}%"]}), 1)
		self.assertNotIn(pending.name, {row.name for row in get_donation_list("pending")["rows"]})
		self.assertIn(pending.name, {row.name for row in get_donation_list("issued")["rows"]})

	def test_new_csr_donations_rejected_but_historical_csr_remains_visible(self):
		self.assertNotIn("CSR", get_donation_workspace()["accounts"]["donation_credit_by_type"])
		with self.assertRaisesRegex(frappe.ValidationError, "Only General donations"):
			register_donation(self._details(donation_purpose="CSR", donor_type="Organisation", receipt_signatory=""))
		historical = frappe.get_doc({
			"doctype": "Donation", "full_name": "Historical CSR Donor", "amount": 50,
			"status": "Success", "source": "Office-online", "donation_purpose": "CSR",
		})
		with manual_donation_write():
			historical.insert(ignore_permissions=True)
		row = next(row for row in get_donation_list()["rows"] if row.name == historical.name)
		self.assertEqual(row.receipt_status, "not_applicable")
		self.assertNotIn(historical.name, {row.name for row in get_donation_list("pending")["rows"]})
		with self.assertRaisesRegex(frappe.ValidationError, "staff-recorded General donations"):
			issue_donation_receipt(historical.name, self.signatory)

	def test_required_donor_details_are_checked_before_posting(self):
		for field in ("donor_name", "address", "pan"):
			with self.subTest(field=field), self.assertRaises(frappe.ValidationError):
				register_donation(self._details(**{field: ""}, receipt_signatory=""))
		with self.assertRaisesRegex(frappe.ValidationError, "valid donor phone number"):
			register_donation(self._details(mobile_number="not-a-phone", receipt_signatory=""))

	def test_credit_ledger_cannot_be_changed(self):
		with self.assertRaisesRegex(frappe.ValidationError, "General Donations credit ledger"):
			register_donation(self._details(donation_account=self.bank))

	def test_cash_80g_over_limit_and_wrong_deposit_account_rejected(self):
		payload = self._details(payment_method="Cash", received_into_account=self.cash,
			receipt_signatory="", donor_signature_data=_drawn_signature())
		payload["donor_signature_proof"] = bind_donation_donor_signature(payload)["proof"]
		recorded = register_donation(payload)
		with self.assertRaisesRegex(frappe.ValidationError, "cash donation over"):
			issue_donation_receipt(recorded["name"], self.signatory, want_80g=1)
		self.assertFalse(frappe.db.get_value("Donation", recorded["name"], "receipt_file"))
		with self.assertRaisesRegex(frappe.ValidationError, "Cash ledger"):
			register_donation(self._details(payment_method="Cash", want_80g=0, donor_signature_data=_drawn_signature()))
		with self.assertRaises(frappe.ValidationError):
			_validate_account(self.bank, use="credit")

	def test_cash_donor_signature_is_bound_to_receipt_details(self):
		payload = self._details(
			payment_method="Cash", received_into_account=self.cash,
			payment_reference="", want_80g=0, donor_signature_data=_drawn_signature(),
		)
		payload["donor_signature_proof"] = bind_donation_donor_signature(payload)["proof"]
		changed = {**payload, "amount": "30001"}
		with self.assertRaisesRegex(frappe.ValidationError, "details changed after the donor signed"):
			register_donation(changed)
		with patch("volunteering.volunteering.donation_portal._receipt_pdf", return_value=b"%PDF-1.4\n%%EOF"), patch(
			"frappe.utils.file_manager.save_file", return_value=frappe._dict(file_url="/private/files/test-donation-receipt.pdf")
		):
			issued = register_donation(payload)
		self.assertTrue(issued["journal_entry"])

	def test_saved_donor_can_be_corrected_and_reused_without_changing_issued_receipt(self):
		with patch("volunteering.volunteering.donation_portal._receipt_pdf", return_value=b"%PDF-1.4\n%%EOF"), patch(
			"frappe.utils.file_manager.save_file", return_value=frappe._dict(file_url="/private/files/test-donation-receipt.pdf")
		):
			first = register_donation(self._details())
			issued = frappe.get_doc("Donation", first["name"])
			update_donation_donor(issued.donor, {
				"donor_name": "Corrected Donor Name", "donor_type": "Individual",
				"address": "Corrected address, Pune 411045", "pan": issued.pan,
				"mobile_number": "", "email": "donor@example.com",
			})
			corrected = frappe.get_doc("Donation Donor", issued.donor)
			second = register_donation(self._details(
				donor=issued.donor, donor_name=corrected.donor_name,
				address=corrected.address, pan=corrected.pan,
				mobile_number=corrected.mobile_number, email=corrected.email,
			))
		self.assertEqual(frappe.get_doc("Donation", first["name"]).full_name, issued.full_name)
		repeated_donation = frappe.get_doc("Donation", second["name"])
		self.assertEqual(repeated_donation.full_name, "Corrected Donor Name")
		self.assertFalse(repeated_donation.mobile_number)
		self.assertEqual(frappe.db.count("Donation Donor", {"name": issued.donor}), 1)

	def test_receipt_pdf_renders_as_private_acknowledgement(self):
		settings = frappe.get_single("Donation Receipt Settings")
		signatory = frappe.get_doc("Donation Receipt Signatory", self.signatory)
		donation = frappe._dict({
			"receipt_number": "RE-2026-00050", "receipt_date": "2026-09-30",
			"amount": 30000, "full_name": "Sample Donor", "address": "Pune, Maharashtra 411045",
			"received_on": "2026-09-30", "donation_purpose": "General", "pan": "BXVPP6265K",
			"mobile_number": "", "email": "", "payment_method": "Online",
			"payment_reference": "IMPS 607216154547", "want_80g": 1,
			"donor_signature_data": "",
		})
		pdf = _receipt_pdf(donation, settings, signatory)
		self.assertTrue(pdf.startswith(b"%PDF"))
		self.assertGreater(len(pdf), 3000)
		if output := os.environ.get("DONATION_RECEIPT_QA_PATH"):
			with open(output, "wb") as handle:
				handle.write(pdf)
