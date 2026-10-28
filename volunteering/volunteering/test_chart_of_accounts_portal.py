"""Permissions and safe structural mutations for the Home Chart of Accounts."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days

from volunteering.volunteering.accounting_test_utils import get_or_create_user
from volunteering.volunteering.chart_of_accounts_portal import (
	LEDGER_PAGE_SIZE,
	SEVAMRITA_COMPANY,
	delete_account,
	get_account_ledger,
	get_chart_of_accounts,
	save_account,
)
from volunteering.volunteering.opening_balances_portal import get_opening_balances, record_opening_balance


class IntegrationTestChartOfAccountsPortal(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.manager = get_or_create_user("coa-manager@example.com", ["Accounts Manager"])
		cls.operator = get_or_create_user("coa-operator@example.com", ["Accounts User"])
		cls.employee = get_or_create_user("coa-employee@example.com", ["Employee"])
		cls.system = get_or_create_user("coa-system@example.com", ["System Manager"])
		cls.project_manager = get_or_create_user("coa-project-manager@example.com", ["Projects Manager"])
		cls.expense_root = frappe.db.get_value(
			"Account",
			{"company": SEVAMRITA_COMPANY, "root_type": "Expense", "parent_account": ["is", "not set"]},
			"name",
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_accounts_users_can_view_but_only_managers_can_edit_chart(self):
		for user in (self.employee, self.system, self.project_manager, "Guest"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				get_chart_of_accounts()
		frappe.set_user(self.operator)
		self.assertFalse(get_chart_of_accounts()["can_manage"])
		with self.assertRaises(frappe.PermissionError):
			save_account({})
		frappe.set_user(self.manager)
		workspace = get_chart_of_accounts()
		self.assertEqual(workspace["company"], SEVAMRITA_COMPANY)
		self.assertTrue(workspace["accounts"])
		self.assertTrue(workspace["can_manage"])

	def test_account_ledger_shows_posted_entries_opening_and_permissions(self):
		frappe.set_user("Administrator")
		asset_root = frappe.db.get_value(
			"Account", {"company": SEVAMRITA_COMPANY, "root_type": "Asset", "parent_account": ["is", "not set"]}, "name"
		)
		account = frappe.get_doc({
			"doctype": "Account", "company": SEVAMRITA_COMPANY, "parent_account": asset_root,
			"account_name": f"Ledger View Test {frappe.generate_hash(length=8)}", "is_group": 0,
		}).insert().name
		frappe.set_user(self.manager)
		opening_date = get_opening_balances()["default_opening_date"]
		record_opening_balance({
			"account": account, "opening_date": opening_date, "side": "Debit",
			"amount": "125.25", "source_reference": "Ledger view test source",
		})
		frappe.set_user(self.operator)
		statement = get_account_ledger(account, opening_date, opening_date)
		self.assertEqual(statement["entry_count"], 1)
		self.assertEqual(statement["opening_balance"], 0)
		self.assertAlmostEqual(statement["total_debit"], 125.25)
		self.assertAlmostEqual(statement["closing_balance"], 125.25)
		self.assertAlmostEqual(statement["entries"][0]["balance"], 125.25)
		later_date = add_days(opening_date, 1)
		later = get_account_ledger(account, later_date, later_date)
		self.assertEqual(later["entry_count"], 0)
		self.assertAlmostEqual(later["opening_balance"], 125.25)
		self.assertAlmostEqual(later["closing_balance"], 125.25)
		with self.assertRaises(frappe.ValidationError):
			get_account_ledger(account, later_date, opening_date)
		with self.assertRaises(frappe.ValidationError):
			get_account_ledger(self.expense_root, opening_date, opening_date)
		frappe.set_user(self.employee)
		with self.assertRaises(frappe.PermissionError):
			get_account_ledger(account, opening_date, opening_date)

	def test_ledger_pagination_preserves_running_balance_and_excludes_cancelled_entries(self):
		frappe.set_user("Administrator")
		parent = frappe.db.get_value("Account", {
			"company": SEVAMRITA_COMPANY, "root_type": "Asset", "parent_account": ["is", "not set"],
		}, "name")
		account = frappe.get_doc({"doctype": "Account", "company": SEVAMRITA_COMPANY,
			"parent_account": parent, "account_name": "QA Ledger Pagination " + frappe.generate_hash(length=8),
		}).insert().name
		# Synthetic rows specifically exercise the read-only statement query.
		# Accounting posting is tested separately through Journal/Payment Entries.
		def entry(index, date, debit=0, credit=0, cancelled=0):
			doc = frappe.get_doc({"doctype": "GL Entry", "company": SEVAMRITA_COMPANY,
				"account": account, "posting_date": date, "debit": debit, "credit": credit,
				"debit_in_account_currency": debit, "credit_in_account_currency": credit,
				"account_currency": "INR", "voucher_type": "Journal Entry",
				"voucher_no": f"QA-QUERY-{index}", "is_cancelled": cancelled,
			})
			doc.db_insert()
		entry("opening", "2026-03-31", debit=25)
		for index in range(LEDGER_PAGE_SIZE + 3):
			entry(index, "2026-04-01", debit=2)
		entry("cancelled", "2026-04-01", debit=999, cancelled=1)
		entry("later", "2026-04-02", debit=888)
		frappe.set_user(self.operator)
		first = get_account_ledger(account, "2026-04-01", "2026-04-01")
		second = get_account_ledger(account, "2026-04-01", "2026-04-01", page=2)
		self.assertEqual(len(first["entries"]), LEDGER_PAGE_SIZE)
		self.assertEqual(len(second["entries"]), 3)
		self.assertEqual(first["entry_count"], LEDGER_PAGE_SIZE + 3)
		self.assertEqual(first["opening_balance"], 25)
		self.assertEqual(first["closing_balance"], 25 + 2 * (LEDGER_PAGE_SIZE + 3))
		for key in ("opening_balance", "closing_balance", "total_debit", "total_credit", "entry_count"):
			self.assertEqual(first[key], second[key], key)
		self.assertEqual(second["entries"][0]["balance"], first["entries"][-1]["balance"] + 2)
		self.assertEqual(second["entries"][-1]["balance"], first["closing_balance"])
		self.assertFalse({row["name"] for row in first["entries"]} & {row["name"] for row in second["entries"]})
		self.assertEqual(get_account_ledger(account, "2026-04-01", "2026-04-01", page=3)["entries"], [])

	def test_ledger_rejects_invalid_dates_pages_and_non_sevamrita_account(self):
		frappe.set_user(self.operator)
		account = next(row["name"] for row in get_chart_of_accounts()["accounts"] if not row["is_group"])
		for value in (0, -1, 10001, "abc", None):
			with self.subTest(page=value), self.assertRaises(frappe.ValidationError):
				get_account_ledger(account, "2026-04-01", "2026-04-02", page=value)
		for start, end in (("", "2026-04-01"), ("not-a-date", "2026-04-01"), ("2026-05-01", "2026-04-01")):
			with self.subTest(start=start, end=end), self.assertRaises(frappe.ValidationError):
				get_account_ledger(account, start, end)
		with self.assertRaises(frappe.PermissionError):
			get_account_ledger("nonexistent-or-other-company-ledger", "2026-04-01", "2026-04-02")

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
