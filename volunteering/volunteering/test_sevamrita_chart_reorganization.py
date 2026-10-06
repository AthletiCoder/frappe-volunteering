"""The Sevamrita chart transition keeps existing references and is repeatable."""

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.donation_accounting_setup import DONATION_INCOME_NAME
from volunteering.volunteering.sevamrita_chart_reorganization import (
	ALIASES,
	MOVES,
	NODES,
	apply_sevamrita_chart,
	preview_sevamrita_chart,
)


class UnitTestSevamritaChartReorganization(UnitTestCase):
	def test_expenses_use_nature_not_direct_indirect(self):
		labels = {label for kind, label, _parent, _group, _type in NODES if kind == "Expense"}
		self.assertIn("Programme Expenses", labels)
		self.assertIn("Travel and Transport", labels)
		self.assertIn("People and Volunteer Costs", labels)
		self.assertNotIn("Food and Groceries", labels)
		self.assertNotIn("Employee Costs", labels)
		self.assertNotIn("Direct Expenses", labels)
		self.assertNotIn("Indirect Expenses", labels)
		self.assertIn(("Expense", "Employee Costs", "People and Volunteer Costs"), MOVES)
		self.assertEqual(DONATION_INCOME_NAME, "General Donations")
		self.assertIn(("Liability", "Creditors", "Supplier Payables", 0), ALIASES)
		self.assertIn(("Asset", "Domestic Bank Account", "Domestic Bank Accounts", 1), ALIASES)
		self.assertIn(("Asset", "Sevamrita Foundation Bank", "SF Axis Bank", 0), ALIASES)
		self.assertIn(("Asset", "FCRA Accounts", "Bank Accounts", 1, ""), NODES)
		self.assertIn(("Asset", "SF Axis Bank", "Domestic Bank Accounts"), MOVES)
		self.assertIn(("Asset", "Cashfree Clearing", "Domestic Bank Accounts"), MOVES)


class IntegrationTestSevamritaChartReorganization(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_preview_is_read_only_and_apply_is_explicit_and_repeatable(self):
		frappe.set_user("Administrator")
		company = "Sevamrita Foundation"
		before = frappe.db.count("Account", {"company": company})
		optional_food_account = frappe.db.exists(
			"Account", {"company": company, "account_name": "Food and Groceries"}
		)
		fcra_group_before = frappe.db.exists(
			"Account", {"company": company, "account_name": "FCRA Accounts"}
		)
		preview = preview_sevamrita_chart()
		self.assertEqual(preview["conflicts"], [])
		self.assertEqual(frappe.db.count("Account", {"company": company}), before)
		with self.assertRaises(frappe.ValidationError):
			apply_sevamrita_chart()

		result = apply_sevamrita_chart(confirmed=True, allow_posted_entries=True)
		self.assertEqual(result["preview"]["conflicts"], [])
		self.assertEqual(
			frappe.db.get_value("Company", company, "default_expense_claim_payable_account"),
			frappe.db.get_value("Account", {"company": company, "account_name": "Employee Reimbursements Payable"}, "name"),
		)
		self.assertEqual(
			frappe.db.get_value("Account", {"company": company, "account_name": "General Donations"}, "parent_account"),
			frappe.db.get_value("Account", {"company": company, "account_name": "Donations and Grants"}, "name"),
		)
		self.assertEqual(
			frappe.db.get_value("Account", {"company": company, "account_name": "Travel Expenses"}, "parent_account"),
			frappe.db.get_value("Account", {"company": company, "account_name": "Travel and Transport"}, "name"),
		)
		self.assertEqual(
			frappe.db.exists("Account", {"company": company, "account_name": "Food and Groceries"}),
			optional_food_account,
		)
		bank_group = frappe.db.get_value(
			"Account", {"company": company, "account_name": "Bank Accounts"}, "name"
		)
		domestic_group = frappe.db.get_value(
			"Account", {"company": company, "account_name": "Domestic Bank Accounts"}, "name"
		)
		fcra_group = frappe.db.get_value(
			"Account", {"company": company, "account_name": "FCRA Accounts"}, "name"
		)
		self.assertEqual(frappe.db.get_value("Account", domestic_group, "parent_account"), bank_group)
		self.assertEqual(frappe.db.get_value("Account", fcra_group, "parent_account"), bank_group)
		self.assertEqual(frappe.db.get_value("Account", fcra_group, "is_group"), 1)
		if not fcra_group_before:
			self.assertEqual(frappe.db.count("Account", {"parent_account": fcra_group}), 0)
		for label in ("SF Axis Bank", "Cashfree Clearing"):
			account = frappe.db.get_value(
				"Account", {"company": company, "account_name": label},
				["parent_account", "account_type"], as_dict=True,
			)
			self.assertEqual(account.parent_account, domestic_group)
			self.assertEqual(account.account_type, "Bank")
		again = apply_sevamrita_chart(confirmed=True, allow_posted_entries=True)
		self.assertEqual(again["renamed"], [])
		self.assertEqual(again["created"], [])
		self.assertEqual(again["moved"], [])
