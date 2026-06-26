# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from unittest.mock import patch

from volunteering.volunteering.accounting_setup import (
	ensure_workflow_actions,
	reload_accounting_workflows,
	setup_accounting_custom_fields,
)
from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department,
	get_or_create_employee,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	make_purchase_order,
)
from volunteering.volunteering.approval_routing import (
	PENDING_PO_TIER_1,
	PENDING_TIER_2,
	PENDING_TIER_3,
)


class IntegrationTestAccountingPOApproval(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.flags.mute_emails = True
		cls._email_patcher = patch("frappe.sendmail")
		cls._email_patcher.start()
		setup_accounting_custom_fields()
		frappe.clear_cache(doctype="Purchase Order")
		reload_accounting_workflows()
		ensure_workflow_actions()

		cls.project = get_or_create_project_with_cost_center()
		cls.employee_email = get_or_create_user(
			"employee-acct@example.com",
			["Employee", "Purchase User"],
			"Employee User",
		)
		cls.accounts_manager_email = get_or_create_user(
			"accounts-mgr-acct@example.com",
			["Employee", "Accounts Manager", "Purchase User"],
			"Accounts Manager",
		)
		cls.board_member_email = get_or_create_user(
			"board-member-acct@example.com",
			["Employee", "NGO Board Member", "Purchase User"],
			"Board Member",
		)
		cls.department = get_or_create_department("Operations")
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		cls.board_member_employee = get_or_create_employee(
			cls.board_member_email, cls.department, "Board Member Employee"
		)

	@classmethod
	def tearDownClass(cls):
		cls._email_patcher.stop()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def tearDown(self):
		frappe.db.delete("Purchase Order", {"project": self.project})
		super().tearDown()

	def _submit_po_as(self, user, amount=1500, owner=None):
		owner = owner or user
		frappe.set_user(user)
		po = make_purchase_order(self.project, amount=amount, owner=owner)
		po = frappe.get_doc("Purchase Order", po.name)
		po.save(ignore_permissions=True)
		apply_workflow(po, "Submit")
		return frappe.get_doc("Purchase Order", po.name)

	def test_low_value_po_routes_to_accounts_review(self):
		po = self._submit_po_as(self.employee_email, amount=1500)
		self.assertEqual(po.workflow_state, PENDING_PO_TIER_1)

	def test_mid_value_po_routes_to_board_member(self):
		po = self._submit_po_as(self.employee_email, amount=5000)
		self.assertEqual(po.workflow_state, PENDING_TIER_2)

	def test_high_value_po_routes_to_board_chair(self):
		po = self._submit_po_as(self.employee_email, amount=15000)
		self.assertEqual(po.workflow_state, PENDING_TIER_3)

	def test_board_member_requester_routes_to_board_member(self):
		po = self._submit_po_as(
			self.board_member_email,
			amount=500,
			owner=self.board_member_email,
		)
		self.assertEqual(po.workflow_state, PENDING_TIER_2)

	def test_accounts_manager_can_approve_low_value_po(self):
		po = self._submit_po_as(self.employee_email, amount=1500)
		frappe.set_user(self.accounts_manager_email)
		approved = frappe.get_doc("Purchase Order", po.name)
		apply_workflow(approved, "Approve")
		approved.reload()
		self.assertEqual(approved.workflow_state, "Approved")
		self.assertEqual(approved.docstatus, 1)

	def test_board_chair_cannot_create_purchase_order(self):
		board_chair_email = get_or_create_user(
			"board-chair-po@example.com",
			["Employee", "NGO Board Chairperson"],
			"Board Chair PO",
		)
		frappe.set_user(board_chair_email)
		with self.assertRaises(frappe.ValidationError):
			make_purchase_order(self.project, amount=500, owner=board_chair_email)
