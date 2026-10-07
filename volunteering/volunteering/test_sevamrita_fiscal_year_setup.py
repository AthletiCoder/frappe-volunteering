"""FY 2024-25 onward remains postable without changing the default year."""

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.patches.keep_sevamrita_fiscal_years_from_2024_active import (
	COMPANY,
	START_YEARS,
	execute,
)


class IntegrationTestSevamritaFiscalYearSetup(IntegrationTestCase):
	def test_existing_disabled_2024_year_is_reactivated(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Company", COMPANY):
			self.skipTest("Sevamrita company is not configured")
		execute()
		fiscal_year = frappe.get_doc("Fiscal Year", "2024-2025")
		fiscal_year.disabled = 1
		fiscal_year.save()

		execute()

		self.assertFalse(frappe.db.get_value("Fiscal Year", "2024-2025", "disabled"))

	def test_years_from_2024_are_active_without_changing_default(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Company", COMPANY):
			self.skipTest("Sevamrita company is not configured")
		default_before = frappe.defaults.get_global_default("fiscal_year")

		execute()
		execute()

		for start_year in START_YEARS:
			with self.subTest(start_year=start_year):
				name = f"{start_year}-{start_year + 1}"
				fiscal_year = frappe.get_doc("Fiscal Year", name)
				self.assertEqual(str(fiscal_year.year_start_date), f"{start_year}-04-01")
				self.assertEqual(str(fiscal_year.year_end_date), f"{start_year + 1}-03-31")
				self.assertFalse(fiscal_year.disabled)
				self.assertTrue(
					not fiscal_year.companies or COMPANY in {row.company for row in fiscal_year.companies}
				)
		self.assertEqual(frappe.defaults.get_global_default("fiscal_year"), default_before)
