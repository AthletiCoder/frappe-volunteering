# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.approval_routing import (
	PENDING_EXPENSE_TIER_1,
	PENDING_PO_TIER_1,
	PENDING_TIER_2,
	PENDING_TIER_3,
	assign_expense_approver,
	get_amount_approval_level,
	get_effective_approval_level,
	get_pending_state_for_level,
	get_requester_minimum_level,
)
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)


class TestApprovalRoutingHelpers(UnitTestCase):
	def test_amount_tiers_use_settings(self):
		settings = get_accounting_settings()
		settings.tier_1_limit = 2000
		settings.tier_2_limit = 10000
		settings.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Volunteering Accounting Settings")

		low = frappe._dict(doctype="Expense Claim", total_claimed_amount=1500)
		mid = frappe._dict(doctype="Expense Claim", total_claimed_amount=5000)
		high = frappe._dict(doctype="Expense Claim", total_claimed_amount=15000)

		self.assertEqual(get_amount_approval_level(low), 1)
		self.assertEqual(get_amount_approval_level(mid), 2)
		self.assertEqual(get_amount_approval_level(high), 3)

	def test_po_amount_tiers_use_grand_total(self):
		doc = frappe._dict(doctype="Purchase Order", grand_total=2500)
		self.assertEqual(get_amount_approval_level(doc), 2)

	def test_pending_state_mapping(self):
		self.assertEqual(
			get_pending_state_for_level("Expense Claim", 1), PENDING_EXPENSE_TIER_1
		)
		self.assertEqual(get_pending_state_for_level("Purchase Order", 1), PENDING_PO_TIER_1)
		self.assertEqual(get_pending_state_for_level("Expense Claim", 2), PENDING_TIER_2)
		self.assertEqual(get_pending_state_for_level("Expense Claim", 3), PENDING_TIER_3)

	@patch("volunteering.volunteering.approval_routing.get_requester_user")
	@patch("volunteering.volunteering.approval_routing.get_user_roles")
	def test_effective_approval_level_for_small_claim(self, mock_roles, mock_requester):
		mock_requester.return_value = "employee@example.com"
		mock_roles.return_value = {"Employee"}
		doc = frappe._dict(
			doctype="Expense Claim",
			total_claimed_amount=1500,
			owner="employee@example.com",
		)
		self.assertEqual(get_effective_approval_level(doc), 1)

	@patch("volunteering.volunteering.approval_routing.get_requester_user")
	@patch("volunteering.volunteering.approval_routing.is_department_head_user")
	def test_department_head_requester_routes_to_board_tier(self, mock_is_head, mock_requester):
		mock_requester.return_value = "head@example.com"
		mock_is_head.return_value = True
		doc = frappe._dict(
			doctype="Expense Claim",
			total_claimed_amount=500,
			employee="EMP-1",
			owner="head@example.com",
		)
		self.assertEqual(get_requester_minimum_level(doc), 2)
		self.assertEqual(get_effective_approval_level(doc), 2)

	@patch("volunteering.volunteering.approval_routing.get_requester_user")
	@patch("volunteering.volunteering.approval_routing.get_user_roles")
	def test_board_chair_cannot_create_requests(self, mock_roles, mock_requester):
		mock_requester.return_value = "chair@example.com"
		mock_roles.return_value = {"NGO Board Chairperson"}
		doc = frappe._dict(doctype="Expense Claim", employee="EMP-1", owner="chair@example.com")
		with self.assertRaises(frappe.ValidationError):
			get_requester_minimum_level(doc)

	@patch("frappe.db.get_value")
	def test_assign_expense_approver_from_department(self, mock_get_value):
		def _get_value(doctype, name, fieldname=None, *args, **kwargs):
			if doctype == "Employee" and name == "EMP-OPS" and fieldname == "department":
				return "Operations"
			if doctype == "Department" and name == "Operations" and fieldname == "department_head":
				return "head@example.com"
			return None

		mock_get_value.side_effect = _get_value
		doc = frappe._dict(doctype="Expense Claim", employee="EMP-OPS")
		assign_expense_approver(doc)
		self.assertEqual(doc.expense_approver, "head@example.com")
