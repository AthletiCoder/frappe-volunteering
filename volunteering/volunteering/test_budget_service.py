# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.budget_service import get_allocated_budget, get_document_amount


class UnitTestBudgetService(UnitTestCase):
	def test_get_document_amount_uses_grand_total_for_po(self):
		doc = frappe._dict(doctype="Purchase Order", grand_total=2500)
		self.assertEqual(get_document_amount(doc), 2500)

	def test_get_document_amount_uses_claimed_amount_for_ec(self):
		doc = frappe._dict(doctype="Expense Claim", total_claimed_amount=1800)
		self.assertEqual(get_document_amount(doc), 1800)

	def test_get_allocated_budget_returns_zero_when_missing(self):
		self.assertEqual(get_allocated_budget("_missing_project", "_missing_dept"), 0)
