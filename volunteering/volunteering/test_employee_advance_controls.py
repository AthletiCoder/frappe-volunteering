# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from volunteering.volunteering.employee_advance_controls import (
	advance_residual_amount,
	advance_residual_ratio,
	is_blocking_advance,
	_validate_max_unsettled,
)


class TestEmployeeAdvanceResidual(UnitTestCase):
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

	def test_unpaid_is_fully_residual_and_blocking(self):
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

	def test_five_percent_residual_allows_replenish(self):
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

	def test_fifteen_percent_residual_blocks(self):
		row = frappe._dict(
			status="Paid",
			advance_amount=1000,
			paid_amount=1000,
			claimed_amount=850,
			return_amount=0,
		)
		self.assertEqual(advance_residual_amount(row), 150)
		self.assertTrue(is_blocking_advance(row, 10))

	def test_exactly_ten_percent_is_not_blocking(self):
		row = frappe._dict(
			status="Paid",
			advance_amount=1000,
			paid_amount=1000,
			claimed_amount=900,
			return_amount=0,
		)
		self.assertFalse(is_blocking_advance(row, 10))

	@patch("volunteering.volunteering.employee_advance_controls.list_open_advances_for_employee")
	@patch("volunteering.volunteering.employee_advance_controls.get_accounting_settings")
	def test_validate_blocks_when_blocking_open(self, mock_settings, mock_list):
		mock_settings.return_value = frappe._dict(
			max_unsettled_advances=1,
			advance_replenish_residual_pct=10,
		)
		mock_list.return_value = [
			frappe._dict(
				name="ADV-1",
				status="Paid",
				advance_amount=1000,
				paid_amount=1000,
				claimed_amount=800,
				return_amount=0,
			)
		]
		doc = frappe._dict(employee="EMP-1", name=None)
		with self.assertRaises(frappe.ValidationError):
			_validate_max_unsettled(doc)

	@patch("volunteering.volunteering.employee_advance_controls.frappe.msgprint")
	@patch("volunteering.volunteering.employee_advance_controls.list_open_advances_for_employee")
	@patch("volunteering.volunteering.employee_advance_controls.get_accounting_settings")
	def test_validate_allows_replenish_with_warning(self, mock_settings, mock_list, mock_msg):
		mock_settings.return_value = frappe._dict(
			max_unsettled_advances=1,
			advance_replenish_residual_pct=10,
		)
		mock_list.return_value = [
			frappe._dict(
				name="ADV-1",
				status="Paid",
				advance_amount=1000,
				paid_amount=1000,
				claimed_amount=960,
				return_amount=0,
			)
		]
		doc = frappe._dict(employee="EMP-1", name=None)
		_validate_max_unsettled(doc)
		mock_msg.assert_called_once()

	@patch("volunteering.volunteering.employee_advance_controls.frappe.msgprint")
	@patch("volunteering.volunteering.employee_advance_controls.list_open_advances_for_employee")
	@patch("volunteering.volunteering.employee_advance_controls.get_accounting_settings")
	def test_fully_claimed_allows_without_warning(self, mock_settings, mock_list, mock_msg):
		mock_settings.return_value = frappe._dict(
			max_unsettled_advances=1,
			advance_replenish_residual_pct=10,
		)
		mock_list.return_value = [
			frappe._dict(
				name="ADV-1",
				status="Claimed",
				advance_amount=1000,
				paid_amount=1000,
				claimed_amount=1000,
				return_amount=0,
			)
		]
		doc = frappe._dict(employee="EMP-1", name=None)
		_validate_max_unsettled(doc)
		mock_msg.assert_not_called()
