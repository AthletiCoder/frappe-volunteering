"""Accounts-only opening balance entries for a staged migration."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from volunteering.volunteering.accounting_test_utils import get_or_create_user
from volunteering.volunteering.chart_of_accounts_portal import SEVAMRITA_COMPANY
from volunteering.volunteering.opening_balances_portal import (
	_amount,
	get_opening_balances,
	record_opening_balance,
)


class IntegrationTestOpeningBalancesPortal(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.manager = get_or_create_user("opening-manager@example.com", ["Accounts Manager"])
		cls.operator = get_or_create_user("opening-operator@example.com", ["Accounts User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _account(self):
		root = frappe.db.get_value("Account", {
			"company": SEVAMRITA_COMPANY, "root_type": "Asset", "parent_account": ["is", "not set"]}, "name")
		return frappe.get_doc({
			"doctype": "Account", "company": SEVAMRITA_COMPANY,
			"parent_account": root, "account_name": f"Opening Test {frappe.generate_hash(length=8)}",
			"is_group": 0,
		}).insert().name

	def test_only_accounts_manager_can_use_opening_balances(self):
		frappe.set_user(self.operator)
		with self.assertRaises(frappe.PermissionError):
			get_opening_balances()
		with self.assertRaises(frappe.PermissionError):
			record_opening_balance({})

	def test_bank_side_posts_once_with_temporary_counterpart(self):
		frappe.set_user("Administrator")
		account = self._account()
		frappe.set_user(self.manager)
		before = get_opening_balances()
		opening_date = before["default_opening_date"]
		details = {"account": account, "opening_date": opening_date, "side": "Debit",
			"amount": "125.25", "source_reference": "Test closing statement"}
		result = record_opening_balance(details)
		je = frappe.get_doc("Journal Entry", result["journal_entry"])
		self.assertEqual(je.docstatus, 1)
		self.assertEqual(je.is_opening, "Yes")
		self.assertEqual(je.voucher_type, "Opening Entry")
		self.assertEqual(len(je.accounts), 2)
		self.assertEqual(je.accounts[0].account, account)
		self.assertEqual(je.accounts[0].debit_in_account_currency, 125.25)
		self.assertEqual(je.accounts[1].account, result["workspace"]["temporary_account"])
		self.assertEqual(je.accounts[1].credit_in_account_currency, 125.25)
		self.assertAlmostEqual(result["workspace"]["temporary_balance"] - before["temporary_balance"], -125.25)
		self.assertTrue(any(row.name == je.name for row in result["workspace"]["history"]))
		with self.assertRaisesRegex(frappe.ValidationError, "opening balance already exists"):
			record_opening_balance(details)

	def test_amount_rejects_invalid_values(self):
		for amount in ("-1", "0", "1.234", "NaN", "Infinity", "wrong"):
			with self.subTest(amount=amount), self.assertRaises(frappe.ValidationError):
				_amount(amount)

	def test_payable_opening_requires_a_named_party(self):
		frappe.set_user("Administrator")
		root = frappe.db.get_value("Account", {
			"company": SEVAMRITA_COMPANY, "root_type": "Liability", "parent_account": ["is", "not set"]}, "name")
		account = frappe.get_doc({
			"doctype": "Account", "company": SEVAMRITA_COMPANY, "parent_account": root,
			"account_name": f"Opening Payable Test {frappe.generate_hash(length=8)}",
			"account_type": "Payable", "is_group": 0,
		}).insert().name
		frappe.set_user(self.manager)
		with self.assertRaisesRegex(frappe.ValidationError, "Choose an existing party"):
			record_opening_balance({
				"account": account, "opening_date": get_opening_balances()["default_opening_date"],
				"side": "Credit", "amount": "40", "source_reference": "Old unpaid bill",
			})
