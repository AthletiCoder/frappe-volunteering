"""Permissions and safe structural mutations for the Home Chart of Accounts."""

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.accounting_test_utils import get_or_create_user
from volunteering.volunteering.chart_of_accounts_portal import (
	SEVAMRITA_COMPANY,
	delete_account,
	get_chart_of_accounts,
	save_account,
)


class IntegrationTestChartOfAccountsPortal(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.manager = get_or_create_user("coa-manager@example.com", ["Accounts Manager"])
		cls.operator = get_or_create_user("coa-operator@example.com", ["Accounts User"])
		cls.employee = get_or_create_user("coa-employee@example.com", ["Employee"])
		cls.expense_root = frappe.db.get_value(
			"Account",
			{"company": SEVAMRITA_COMPANY, "root_type": "Expense", "parent_account": ["is", "not set"]},
			"name",
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_only_accounts_manager_and_administrator_can_open_workspace(self):
		for user in (self.operator, self.employee, "Guest"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				get_chart_of_accounts()
		frappe.set_user(self.manager)
		workspace = get_chart_of_accounts()
		self.assertEqual(workspace["company"], SEVAMRITA_COMPANY)
		self.assertTrue(workspace["accounts"])

	def test_manager_can_create_rename_disable_and_remove_unused_accounts(self):
		frappe.set_user(self.manager)
		suffix = frappe.generate_hash(length=8)
		group_name = f"Portal Test Group {suffix}"
		created_group = save_account(
			{
				"account_name": group_name,
				"account_number": "",
				"parent_account": self.expense_root,
				"is_group": 1,
			}
		)
		group = created_group["saved_account"]
		self.assertTrue(frappe.db.exists("Account", group))

		ledger_name = f"Portal Test Ledger {suffix}"
		created_ledger = save_account(
			{
				"account_name": ledger_name,
				"account_number": "",
				"parent_account": group,
				"is_group": 0,
				"account_type": "Expense Account",
				"account_currency": "INR",
			}
		)
		ledger = created_ledger["saved_account"]
		row = next(item for item in created_ledger["accounts"] if item["name"] == ledger)

		renamed = save_account(
			{
				"account_name": f"Renamed Portal Ledger {suffix}",
				"account_number": "",
				"parent_account": group,
				"is_group": 0,
				"account_type": "Expense Account",
				"account_currency": "INR",
				"disabled": 1,
			},
			account=ledger,
			expected_modified=row["modified"],
		)
		renamed_ledger = renamed["saved_account"]
		self.assertNotEqual(renamed_ledger, ledger)
		self.assertEqual(frappe.db.get_value("Account", renamed_ledger, "disabled"), 1)

		row = next(item for item in renamed["accounts"] if item["name"] == renamed_ledger)
		deleted_ledger = delete_account(renamed_ledger, row["modified"])
		self.assertFalse(frappe.db.exists("Account", renamed_ledger))
		group_row = next(item for item in deleted_ledger["accounts"] if item["name"] == group)
		delete_account(group, group_row["modified"])
		self.assertFalse(frappe.db.exists("Account", group))

	def test_root_accounts_and_group_kind_are_protected(self):
		frappe.set_user(self.manager)
		root = next(row for row in get_chart_of_accounts()["accounts"] if row["name"] == self.expense_root)
		with self.assertRaisesRegex(frappe.ValidationError, "Root accounts cannot be edited"):
			save_account(
				{
					"account_name": root["account_name"],
					"parent_account": self.expense_root,
					"is_group": 1,
				},
					account=self.expense_root,
					expected_modified=root["modified"],
				)
