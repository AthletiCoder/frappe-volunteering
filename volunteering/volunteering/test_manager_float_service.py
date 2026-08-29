# Copyright (c) 2026, Vadiraj Tirtha Das and contributors

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.manager_float_service import (
	REIMBURSEMENT_MANAGER_ADVANCE,
	is_manager_float_claim,
	list_fundable_manager_advances,
	manager_float_funding_status,
	pick_manager_advance,
)


class TestManagerFloatService(IntegrationTestCase):
	def test_is_manager_float_claim(self):
		self.assertFalse(is_manager_float_claim(frappe._dict(reimbursement_source="Out of Pocket")))
		self.assertTrue(is_manager_float_claim(frappe._dict(reimbursement_source=REIMBURSEMENT_MANAGER_ADVANCE)))

	def test_list_fundable_manager_advances_empty_without_paid(self):
		rows = list_fundable_manager_advances("__no_such_employee__")
		self.assertEqual(rows, [])

	def test_manager_float_funding_status_without_manager(self):
		status = manager_float_funding_status(
			frappe._dict(
				employee="__no_such__",
				reimbursement_source=REIMBURSEMENT_MANAGER_ADVANCE,
				total_claimed_amount=100,
			)
		)
		self.assertFalse(status["eligible"])
		self.assertIn("reporting manager", status["message"].lower())

	def test_pick_manager_advance_returns_none_when_empty(self):
		self.assertIsNone(pick_manager_advance("__no_such__", 100))
