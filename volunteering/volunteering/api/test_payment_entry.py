# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Tests for Payment Entry helper around donations."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.api.donations import _make_status_token
from volunteering.volunteering.api.payment_entry import create_payment_entry_for_donation
from volunteering.volunteering.api.volunteer_donor import upsert_volunteer_for_donation
from volunteering.volunteering.test_utils import unique_mobile


class IntegrationTestDonationPaymentEntry(IntegrationTestCase):
	def _donation(self, status="Success"):
		mobile = unique_mobile("82")
		volunteer, _ = upsert_volunteer_for_donation(
			full_name="PE Donor",
			mobile_number=mobile,
			email=f"pe-{frappe.generate_hash(length=6)}@example.com",
		)
		doc = frappe.get_doc(
			{
				"doctype": "Donation",
				"full_name": "PE Donor",
				"email": f"pe-{frappe.generate_hash(length=6)}@example.com",
				"mobile_number": mobile,
				"amount": 150,
				"currency": "INR",
				"status": status,
				"source": "Gateway",
				"volunteer": volunteer,
				"cashfree_order_id": f"ORD-PE-{frappe.generate_hash(length=8)}",
			}
		).insert(ignore_permissions=True)
		doc.db_set("status_token", _make_status_token(doc.name), update_modified=False)
		return doc

	def test_skips_when_not_success(self):
		doc = self._donation(status="Pending")
		self.assertIsNone(create_payment_entry_for_donation(doc.name))

	def test_skips_when_already_has_payment_entry(self):
		doc = self._donation(status="Success")
		doc.db_set("payment_entry", "PE-EXISTING", update_modified=False)
		self.assertEqual(create_payment_entry_for_donation(doc.name), "PE-EXISTING")

	def test_skips_when_auto_create_disabled(self):
		frappe.db.set_single_value("Cashfree Settings", "create_payment_entry", 0)
		doc = self._donation(status="Success")
		self.assertIsNone(create_payment_entry_for_donation(doc.name))

	@patch("volunteering.volunteering.api.payment_entry._party_receivable_account")
	@patch("volunteering.volunteering.api.payment_entry.ensure_customer_for_volunteer")
	def test_creates_receive_pe_when_enabled(self, mock_customer, mock_recv):
		settings = frappe.get_single("Cashfree Settings")
		if not settings.company or not settings.mode_of_payment or not settings.paid_to_account:
			self.skipTest("Cashfree accounting defaults not configured on this site")

		frappe.db.set_single_value("Cashfree Settings", "create_payment_entry", 1)
		mock_customer.return_value = "CUST-TEST"
		mock_recv.return_value = "Debtors - SF"

		doc = self._donation(status="Success")
		pe = MagicMockPE()

		real_new_doc = frappe.new_doc

		def _new_doc(doctype, *args, **kwargs):
			if doctype == "Payment Entry":
				return pe
			return real_new_doc(doctype, *args, **kwargs)

		with patch("volunteering.volunteering.api.payment_entry.frappe.new_doc", side_effect=_new_doc):
			result = create_payment_entry_for_donation(doc.name)

		self.assertEqual(result, "PE-MOCK-1")
		doc.reload()
		self.assertEqual(doc.payment_entry, "PE-MOCK-1")
		self.assertTrue(pe._submitted)


class MagicMockPE:
	def __init__(self):
		self.payment_type = None
		self.company = None
		self.posting_date = None
		self.mode_of_payment = None
		self.party_type = None
		self.party = None
		self.paid_from = None
		self.paid_to = None
		self.paid_amount = None
		self.received_amount = None
		self.target_exchange_rate = None
		self.source_exchange_rate = None
		self.paid_from_account_currency = None
		self.paid_to_account_currency = None
		self.reference_no = None
		self.reference_date = None
		self.remarks = None
		self.name = "PE-MOCK-1"
		self._submitted = False

	def set_missing_values(self):
		return

	def set_exchange_rate(self):
		return

	def set_amounts(self):
		return

	def insert(self, ignore_permissions=False):
		return self

	def submit(self):
		self._submitted = True
		return self
