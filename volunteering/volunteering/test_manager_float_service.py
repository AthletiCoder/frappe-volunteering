# Copyright (c) 2026, Vadiraj Tirtha Das and contributors

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.manager_float_service import (
	REIMBURSEMENT_MANAGER_ADVANCE,
	_validate_employee_has_no_blocking_advance_for_manager_float,
	is_manager_float_claim,
	list_fundable_manager_advances,
	manager_float_funding_status,
	pick_manager_advance,
	validate_manager_float_expense_claim,
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

	@patch("volunteering.volunteering.manager_float_service.get_direct_manager_employee")
	@patch("volunteering.volunteering.manager_float_service.list_open_advances_for_employee")
	@patch(
		"volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings.get_accounting_settings"
	)
	def test_manager_float_blocked_when_employee_has_blocking_paid_advance(
		self, mock_settings, mock_list, mock_manager
	):
		mock_settings.return_value = frappe._dict(advance_replenish_residual_pct=10)
		mock_manager.return_value = "MGR-1"
		mock_list.return_value = [
			frappe._dict(
				name="ADV-OWN-1",
				docstatus=1,
				status="Paid",
				advance_amount=1000,
				paid_amount=1000,
				claimed_amount=800,
				return_amount=0,
			)
		]
		doc = frappe._dict(
			doctype="Expense Claim",
			employee="EMP-1",
			reimbursement_source=REIMBURSEMENT_MANAGER_ADVANCE,
			docstatus=0,
			workflow_state="Draft",
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_manager_float_expense_claim(doc)
		self.assertIn("ADV-OWN-1", str(ctx.exception))
		self.assertIn("Get Advances", str(ctx.exception))

	@patch("volunteering.volunteering.manager_float_service.list_open_advances_for_employee")
	@patch(
		"volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings.get_accounting_settings"
	)
	def test_manager_float_allowed_when_own_advance_fully_settled(self, mock_settings, mock_list):
		mock_settings.return_value = frappe._dict(advance_replenish_residual_pct=10)
		mock_list.return_value = [
			frappe._dict(
				name="ADV-OWN-1",
				docstatus=1,
				status="Claimed",
				advance_amount=1000,
				paid_amount=1000,
				claimed_amount=1000,
				return_amount=0,
			)
		]
		doc = frappe._dict(employee="EMP-1")
		_validate_employee_has_no_blocking_advance_for_manager_float(doc)
