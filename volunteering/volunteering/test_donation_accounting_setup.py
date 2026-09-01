# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Tests for donation accounting migrate helpers."""

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.donation_accounting_setup import (
	CASHFREE_CLEARING_NAME,
	CASHFREE_MODE_OF_PAYMENT,
	DONATION_INCOME_NAME,
	ensure_donation_accounting,
)


class IntegrationTestDonationAccountingSetup(IntegrationTestCase):
	def test_ensure_donation_accounting_is_idempotent(self):
		if not frappe.db.exists("DocType", "Account"):
			self.skipTest("Accounts not installed")

		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No company on site")

		ensure_donation_accounting()
		clearing_1 = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": CASHFREE_CLEARING_NAME, "is_group": 0},
			"name",
		)
		income_1 = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": DONATION_INCOME_NAME, "is_group": 0},
			"name",
		)

		ensure_donation_accounting()
		clearing_2 = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": CASHFREE_CLEARING_NAME, "is_group": 0},
			"name",
		)
		income_2 = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": DONATION_INCOME_NAME, "is_group": 0},
			"name",
		)

		self.assertEqual(clearing_1, clearing_2)
		self.assertEqual(income_1, income_2)
		self.assertTrue(clearing_1)
		self.assertTrue(income_1)
		self.assertTrue(frappe.db.exists("Mode of Payment", CASHFREE_MODE_OF_PAYMENT))

		settings = frappe.get_single("Cashfree Settings")
		self.assertEqual(settings.company, company)
		self.assertEqual(settings.paid_to_account, clearing_1)
		self.assertEqual(settings.income_account, income_1)
		self.assertEqual(settings.mode_of_payment, CASHFREE_MODE_OF_PAYMENT)
