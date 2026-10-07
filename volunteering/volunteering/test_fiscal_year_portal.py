"""System-Manager-only Fiscal Year setup from the Home workspace."""

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.accounting_test_utils import get_or_create_user
from volunteering.volunteering.fiscal_year_portal import (
	COMPANY,
	activate_fiscal_year,
	create_fiscal_year,
	get_fiscal_year_workspace,
)


class IntegrationTestFiscalYearPortal(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.system = get_or_create_user("fiscal-home-system@example.com", ["System Manager"], "Fiscal Home System")
		cls.accounts = get_or_create_user("fiscal-home-accounts@example.com", ["Accounts Manager"], "Fiscal Home Accounts")

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_system_manager_can_create_and_reactivate_without_closing_current_year(self):
		frappe.set_user(self.system)
		before = frappe.db.get_value("Fiscal Year", "2026-2027", "disabled")
		default_before = frappe.defaults.get_global_default("fiscal_year")
		workspace = create_fiscal_year("2042")
		created = frappe.get_doc("Fiscal Year", "2042-2043")
		self.assertEqual(str(created.year_start_date), "2042-04-01")
		self.assertEqual(str(created.year_end_date), "2043-03-31")
		self.assertFalse(created.disabled)
		self.assertEqual({row.company for row in created.companies}, {COMPANY})
		self.assertIn("2042-2043", {row["name"] for row in workspace["years"]})
		self.assertEqual(frappe.db.get_value("Fiscal Year", "2026-2027", "disabled"), before)
		self.assertEqual(frappe.defaults.get_global_default("fiscal_year"), default_before)

		frappe.set_user("Administrator")
		created.disabled = 1
		created.save()
		frappe.set_user(self.system)
		row = next(row for row in get_fiscal_year_workspace()["years"] if row["name"] == "2042-2043")
		self.assertFalse(row["active"])
		self.assertTrue(row["can_activate"])
		workspace = activate_fiscal_year("2042-2043")
		self.assertTrue(next(row for row in workspace["years"] if row["name"] == "2042-2043")["active"])
		self.assertEqual(frappe.db.get_value("Fiscal Year", "2026-2027", "disabled"), before)
		self.assertEqual(frappe.defaults.get_global_default("fiscal_year"), default_before)

	def test_accounts_manager_cannot_manage_fiscal_years(self):
		frappe.set_user(self.accounts)
		for action in (
			get_fiscal_year_workspace,
			lambda: create_fiscal_year("2042"),
			lambda: activate_fiscal_year("2026-2027"),
		):
			with self.subTest(action=action), self.assertRaises(frappe.PermissionError):
				action()

	def test_invalid_year_and_duplicate_are_rejected(self):
		frappe.set_user(self.system)
		for value in ("2025-2026", "1999", "2099", "2025.5", "2026x"):
			with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
				create_fiscal_year(value)
		with self.assertRaises(frappe.ValidationError):
			create_fiscal_year("2026")
