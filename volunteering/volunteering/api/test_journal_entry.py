# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Tests for donation income Journal Entry helper."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.api.donations import _make_status_token
from volunteering.volunteering.api.journal_entry import create_income_journal_entry_for_donation
from volunteering.volunteering.api.volunteer_donor import upsert_volunteer_for_donation
from volunteering.volunteering.test_utils import unique_mobile


class IntegrationTestDonationJournalEntry(IntegrationTestCase):
	def _donation(self, status="Success", payment_entry="PE-TEST-1", journal_entry=None):
		mobile = unique_mobile("83")
		volunteer, _ = upsert_volunteer_for_donation(
			full_name="JE Donor",
			mobile_number=mobile,
			email=f"je-{frappe.generate_hash(length=6)}@example.com",
		)
		doc = frappe.get_doc(
			{
				"doctype": "Donation",
				"full_name": "JE Donor",
				"email": f"je-{frappe.generate_hash(length=6)}@example.com",
				"mobile_number": mobile,
				"amount": 200,
				"currency": "INR",
				"status": status,
				"source": "Gateway",
				"volunteer": volunteer,
				"cashfree_order_id": f"ORD-JE-{frappe.generate_hash(length=8)}",
			}
		).insert(ignore_permissions=True)
		doc.db_set("status_token", _make_status_token(doc.name), update_modified=False)
		if payment_entry:
			doc.db_set("payment_entry", payment_entry, update_modified=False)
		if journal_entry:
			doc.db_set("journal_entry", journal_entry, update_modified=False)
		doc.reload()
		return doc

	def test_skips_without_payment_entry(self):
		doc = self._donation(payment_entry=None)
		self.assertIsNone(create_income_journal_entry_for_donation(doc.name))

	def test_skips_when_already_has_journal_entry(self):
		doc = self._donation(journal_entry="JE-EXISTING")
		self.assertEqual(create_income_journal_entry_for_donation(doc.name), "JE-EXISTING")

	def test_skips_when_auto_create_disabled(self):
		frappe.db.set_single_value("Cashfree Settings", "create_payment_entry", 0)
		doc = self._donation()
		self.assertIsNone(create_income_journal_entry_for_donation(doc.name))

	@patch("volunteering.volunteering.api.journal_entry._party_receivable_account")
	def test_creates_income_je_when_enabled(self, mock_recv):
		settings = frappe.get_single("Cashfree Settings")
		if not settings.company or not settings.income_account:
			self.skipTest("Cashfree accounting defaults not configured on this site")

		frappe.db.set_single_value("Cashfree Settings", "create_payment_entry", 1)
		mock_recv.return_value = "Debtors - SF"
		doc = self._donation()
		doc.db_set("customer", "CUST-TEST", update_modified=False)

		je = MagicMockJE()
		real_new_doc = frappe.new_doc

		def _new_doc(doctype, *args, **kwargs):
			if doctype == "Journal Entry":
				return je
			return real_new_doc(doctype, *args, **kwargs)

		with patch("volunteering.volunteering.api.journal_entry.frappe.new_doc", side_effect=_new_doc):
			result = create_income_journal_entry_for_donation(doc.name)

		self.assertEqual(result, "JE-MOCK-1")
		doc.reload()
		self.assertEqual(doc.journal_entry, "JE-MOCK-1")
		self.assertTrue(je._submitted)


class MagicMockJE:
	def __init__(self):
		self.voucher_type = None
		self.company = None
		self.posting_date = None
		self.user_remark = None
		self.cheque_no = None
		self.cheque_date = None
		self.accounts = []
		self.name = "JE-MOCK-1"
		self._submitted = False

	def append(self, field, row):
		self.accounts.append(row)

	def insert(self, ignore_permissions=False):
		return self

	def submit(self):
		self._submitted = True
		return self
