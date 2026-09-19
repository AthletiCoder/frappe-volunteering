# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.employee_advance_controls import (
	advance_approval_outstanding_amount,
	advance_counts_towards_approval_exposure,
	advance_residual_amount,
	advance_residual_ratio,
	is_blocking_advance,
)


class TestEmployeeAdvanceResidual(UnitTestCase):
	def test_approval_exposure_includes_approved_unpaid_remainder(self):
		row = frappe._dict(
			status="Partially Paid",
			workflow_state="Approved",
			docstatus=1,
			advance_amount=5000,
			paid_amount=1000,
			claimed_amount=100,
			return_amount=200,
		)
		self.assertEqual(advance_residual_amount(row), 700)
		self.assertEqual(advance_approval_outstanding_amount(row), 4700)
		self.assertTrue(advance_counts_towards_approval_exposure(row))
		row.docstatus = 2
		self.assertFalse(advance_counts_towards_approval_exposure(row))
		self.assertEqual(advance_approval_outstanding_amount(row), 0)

	def test_only_active_requests_and_unsettled_advances_count_towards_approval(self):
		base = {
			"advance_amount": 1000,
			"paid_amount": 0,
			"claimed_amount": 0,
			"return_amount": 0,
			"status": "Unpaid",
			"docstatus": 0,
		}
		for workflow_state, expected in (
			("Draft", False),
			("Rejected", False),
			("Pending Approval", True),
			("Pending Board Member", True),
			("Approved", True),
		):
			with self.subTest(workflow_state=workflow_state):
				row = frappe._dict({**base, "workflow_state": workflow_state})
				self.assertEqual(advance_counts_towards_approval_exposure(row), expected)

		settled = frappe._dict(
			{
				**base,
				"docstatus": 1,
				"workflow_state": "Approved",
				"status": "Claimed",
				"paid_amount": 1000,
				"claimed_amount": 1000,
			}
		)
		self.assertFalse(advance_counts_towards_approval_exposure(settled))

	def test_settled_paid_portion_does_not_release_approved_unpaid_remainder(self):
		for status, claimed, returned in (
			("Claimed", 1000, 0),
			("Returned", 0, 1000),
			("Partly Claimed and Returned", 400, 600),
		):
			with self.subTest(status=status):
				row = frappe._dict(
					status=status,
					workflow_state="Approved",
					docstatus=1,
					advance_amount=5000,
					paid_amount=1000,
					claimed_amount=claimed,
					return_amount=returned,
				)
				self.assertEqual(advance_residual_amount(row), 0)
				self.assertEqual(advance_approval_outstanding_amount(row), 4000)
				self.assertTrue(advance_counts_towards_approval_exposure(row))
				row.paid_amount = row.advance_amount
				row.claimed_amount = row.advance_amount - returned
				self.assertEqual(advance_approval_outstanding_amount(row), 0)
				self.assertFalse(advance_counts_towards_approval_exposure(row))

	def test_fully_claimed_has_zero_residual(self):
		row = frappe._dict(
			status="Claimed",
			advance_amount=1000,
			paid_amount=1000,
			claimed_amount=1000,
			return_amount=0,
		)
		self.assertEqual(advance_residual_amount(row), 0)
		self.assertFalse(is_blocking_advance(row, 10))

	def test_returned_has_zero_residual(self):
		row = frappe._dict(
			status="Returned",
			advance_amount=1000,
			paid_amount=1000,
			claimed_amount=0,
			return_amount=1000,
		)
		self.assertEqual(advance_residual_amount(row), 0)
		self.assertFalse(is_blocking_advance(row, 10))

	def test_unpaid_has_full_residual_for_manager_float_selection(self):
		row = frappe._dict(
			status="Unpaid",
			advance_amount=5000,
			paid_amount=0,
			claimed_amount=0,
			return_amount=0,
		)
		self.assertEqual(advance_residual_amount(row), 5000)
		self.assertEqual(advance_residual_ratio(row), 1.0)
		self.assertTrue(is_blocking_advance(row, 10))

	def test_five_percent_residual_calculation(self):
		row = frappe._dict(
			status="Paid",
			advance_amount=1000,
			paid_amount=1000,
			claimed_amount=950,
			return_amount=0,
		)
		self.assertEqual(advance_residual_amount(row), 50)
		self.assertAlmostEqual(advance_residual_ratio(row), 0.05)
		self.assertFalse(is_blocking_advance(row, 10))

	def test_fifteen_percent_residual_prefers_own_advance_for_expense_claim(self):
		row = frappe._dict(
			status="Paid",
			advance_amount=1000,
			paid_amount=1000,
			claimed_amount=850,
			return_amount=0,
		)
		self.assertEqual(advance_residual_amount(row), 150)
		self.assertTrue(is_blocking_advance(row, 10))

	def test_exactly_ten_percent_does_not_block_manager_float_source(self):
		row = frappe._dict(
			status="Paid",
			advance_amount=1000,
			paid_amount=1000,
			claimed_amount=900,
			return_amount=0,
		)
		self.assertFalse(is_blocking_advance(row, 10))
