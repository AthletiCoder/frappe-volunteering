"""Preview and guardrails for the Section 8 account template."""

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.section8_chart import NODES, apply_section8_chart, preview_section8_chart


class UnitTestSection8Chart(UnitTestCase):
	def test_template_covers_four_major_roots_and_donation_types(self):
		self.assertEqual({row[0] for row in NODES}, {"Asset", "Liability", "Income", "Expense"})
		self.assertTrue({"General Donations", "Corpus Donations", "Restricted Donations / Grants", "CSR Grants"}.issubset({row[2] for row in NODES}))
		self.assertEqual(next(row for row in NODES if row[2] == "GST Payable / Input GST")[3], 1)


class IntegrationTestSection8Chart(IntegrationTestCase):
	def test_preview_is_read_only_and_apply_requires_explicit_confirmation(self):
		before = frappe.db.count("Account", {"company": "Sevamrita Foundation"})
		preview = preview_section8_chart()
		self.assertEqual(preview["company"], "Sevamrita Foundation")
		self.assertFalse(preview["has_conflicts"])
		self.assertFalse(any(row["label"].startswith("FCRA") for row in preview["nodes"]))
		with self.assertRaises(frappe.ValidationError):
			apply_section8_chart()
		self.assertEqual(frappe.db.count("Account", {"company": "Sevamrita Foundation"}), before)

	def test_confirmed_apply_is_additive_and_repeatable_in_test_transaction(self):
		before = preview_section8_chart()
		result = apply_section8_chart(confirmed=True)
		self.assertEqual(len(result["created"]), sum(row["status"] == "create" for row in before["nodes"]))
		self.assertFalse(result["preview"]["has_conflicts"])
		self.assertTrue(frappe.db.exists("Account", {"company": "Sevamrita Foundation", "account_name": "General Donations"}))
		again = apply_section8_chart(confirmed=True)
		self.assertEqual(again["created"], [])
