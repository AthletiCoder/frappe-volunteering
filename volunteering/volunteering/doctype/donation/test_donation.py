# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Unit + integration tests for Donation DocType validation."""

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.doctype.donation.donation import PAN_RE
from volunteering.volunteering.test_utils import unique_mobile

# Currency → Fiscal Year fixtures conflict with India FY on this site
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Volunteer",
	"Company",
	"User",
	"Customer",
	"Currency",
	"Fiscal Year",
	"Payment Entry",
]


class TestDonationPanUnit(UnitTestCase):
	def test_valid_pan(self):
		self.assertTrue(PAN_RE.match("ABCDE1234F"))
		self.assertTrue(PAN_RE.match("AAAAA0000A"))

	def test_invalid_pan(self):
		self.assertFalse(PAN_RE.match("ABCDE12345"))
		self.assertFalse(PAN_RE.match("abcde1234f"))
		self.assertFalse(PAN_RE.match("ABCD1234F"))
		self.assertFalse(PAN_RE.match(""))


class IntegrationTestDonation(IntegrationTestCase):
	def _make_donation(self, **overrides):
		payload = {
			"doctype": "Donation",
			"full_name": "Test Donor",
			"email": f"donor-{frappe.generate_hash(length=6)}@example.com",
			"mobile_number": unique_mobile("91"),
			"amount": 100,
			"currency": "INR",
			"status": "Initiated",
			"source": "Gateway",
			"want_80g": 0,
		}
		payload.update(overrides)
		return frappe.get_doc(payload)

	def test_insert_normalizes_mobile(self):
		mobile = unique_mobile("92").replace("+91-", "")
		doc = self._make_donation(mobile_number=mobile)
		doc.insert(ignore_permissions=True)
		self.assertTrue(doc.mobile_number.startswith("+91-"))
		self.assertEqual(len(doc.mobile_number.replace("+91-", "")), 10)

	def test_amount_must_be_positive(self):
		doc = self._make_donation(amount=0)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_80g_requires_valid_pan_and_address(self):
		doc = self._make_donation(want_80g=1, pan="BADPAN", address="Somewhere")
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

		doc = self._make_donation(want_80g=1, pan="ABCDE1234F", address="")
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

		doc = self._make_donation(
			want_80g=1, pan="abcde1234f", address="12 Test Street, Hyderabad"
		)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.pan, "ABCDE1234F")

	def test_without_80g_pan_optional(self):
		doc = self._make_donation(want_80g=0, pan="", address="")
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.status, "Initiated")
