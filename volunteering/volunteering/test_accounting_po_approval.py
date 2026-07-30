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
	delete_documents_with_workflow_actions,
	ensure_designations,
	get_or_create_department,
	get_or_create_employee,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	make_purchase_order,
)
from volunteering.volunteering.approval_routing import (
	PENDING_APPROVAL,
	get_fallback_board_approver,
)


class IntegrationTestAccountingPOApproval(IntegrationTestCase):
	"""Designation + reports_to approval flow for Purchase Orders.

	Chain: requester (Associate, approve 0) -> manager (Manager, approve 2000)
	-> director (Director, approve 25000). The workflow fixture routes
	Draft -> Pending Approval and gates Approve on `pending_approver`, so
	routing is asserted through that field rather than through per-tier states.

	Every user needs `Purchase User`: ERPNext's own party/account validation
	runs before the volunteering hooks and would otherwise raise PermissionError.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.flags.mute_emails = True
		cls._email_patcher = patch("frappe.sendmail")
		cls._email_patcher.start()
		cls._prev_designation_flag = frappe.db.get_single_value(
			"Volunteering Accounting Settings", "use_designation_approval"
		)
		frappe.db.set_single_value(
			"Volunteering Accounting Settings", "use_designation_approval", 1
		)
		frappe.clear_cache(doctype="Volunteering Accounting Settings")
		setup_accounting_custom_fields()
		frappe.clear_cache(doctype="Purchase Order")
		reload_accounting_workflows()
		ensure_workflow_actions()

		ensure_designations("Associate", "Manager", "Director")

		cls.project = get_or_create_project_with_cost_center()
		cls.requester_email = get_or_create_user(
			"po-requester@example.com", ["Employee", "Purchase User"], "PO Requester"
		)
		cls.manager_email = get_or_create_user(
			"po-manager@example.com", ["Employee", "Purchase User"], "PO Manager"
		)
		cls.director_email = get_or_create_user(
			"po-director@example.com", ["Employee", "Purchase User"], "PO Director"
		)
		cls.unmanaged_email = get_or_create_user(
			"po-unmanaged@example.com", ["Employee", "Purchase User"], "PO Unmanaged"
		)
		cls.board_chair_email = get_or_create_user(
			"board-chair-po@example.com",
			["Employee", "NGO Board Chairperson", "Purchase User"],
			"Board Chair PO",
		)

		cls.department = get_or_create_department("Operations")
		cls.requester_employee = get_or_create_employee(
			cls.requester_email, cls.department, "PO Requester Employee"
		)
		cls.manager_employee = get_or_create_employee(
			cls.manager_email, cls.department, "PO Manager Employee"
		)
		cls.director_employee = get_or_create_employee(
			cls.director_email, cls.department, "PO Director Employee"
		)
		cls.unmanaged_employee = get_or_create_employee(
			cls.unmanaged_email, cls.department, "PO Unmanaged Employee"
		)

		frappe.db.set_value(
			"Employee",
			cls.director_employee,
			{"designation": "Director", "reports_to": None},
		)
		frappe.db.set_value(
			"Employee",
			cls.manager_employee,
			{"designation": "Manager", "reports_to": cls.director_employee},
		)
		frappe.db.set_value(
			"Employee",
			cls.requester_employee,
			{"designation": "Associate", "reports_to": cls.manager_employee},
		)
		frappe.db.set_value(
			"Employee",
			cls.unmanaged_employee,
			{"designation": "Associate", "reports_to": None},
		)

	@classmethod
	def tearDownClass(cls):
		cls._email_patcher.stop()
		frappe.flags.mute_emails = False
		frappe.db.set_single_value(
			"Volunteering Accounting Settings",
			"use_designation_approval",
			1 if cls._prev_designation_flag is None else cls._prev_designation_flag,
		)
		frappe.clear_cache(doctype="Volunteering Accounting Settings")
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")
		delete_documents_with_workflow_actions("Purchase Order", {"project": self.project})
		super().tearDown()

	def _submit_po_as(self, user, amount=1500, owner=None):
		owner = owner or user
		frappe.set_user(user)
		po = make_purchase_order(self.project, amount=amount, owner=owner)
		po = frappe.get_doc("Purchase Order", po.name)
		po.save(ignore_permissions=True)
		apply_workflow(po, "Submit")
		return frappe.get_doc("Purchase Order", po.name)

	def test_low_value_po_routes_to_manager(self):
		po = self._submit_po_as(self.requester_email, amount=1500)
		self.assertEqual(po.workflow_state, PENDING_APPROVAL)
		self.assertEqual(po.pending_approver, self.manager_email)

	def test_mid_value_po_routes_past_manager_to_director(self):
		# 5000 exceeds Manager's 2000 approval authority; Director (25000) can.
		po = self._submit_po_as(self.requester_email, amount=5000)
		self.assertEqual(po.workflow_state, PENDING_APPROVAL)
		self.assertEqual(po.pending_approver, self.director_email)

	def test_high_value_po_lands_with_first_manager(self):
		# 30000 exceeds everyone in the chain; the immediate manager receives it
		# and must escalate.
		po = self._submit_po_as(self.requester_email, amount=30000)
		self.assertEqual(po.workflow_state, PENDING_APPROVAL)
		self.assertEqual(po.pending_approver, self.manager_email)

	def test_po_without_reporting_chain_falls_back_to_board(self):
		po = self._submit_po_as(self.unmanaged_email, amount=1500)
		self.assertEqual(po.workflow_state, PENDING_APPROVAL)
		self.assertNotEqual(po.pending_approver, self.unmanaged_email)
		self.assertEqual(po.pending_approver, get_fallback_board_approver())

	def test_manager_can_approve_low_value_po(self):
		po = self._submit_po_as(self.requester_email, amount=1500)
		frappe.set_user(self.manager_email)
		approved = frappe.get_doc("Purchase Order", po.name)
		apply_workflow(approved, "Approve")
		approved.reload()
		self.assertEqual(approved.workflow_state, "Approved")
		self.assertEqual(approved.docstatus, 1)

	def test_manager_cannot_approve_beyond_designation_limit(self):
		po = self._submit_po_as(self.requester_email, amount=30000)
		frappe.set_user(self.manager_email)
		doc = frappe.get_doc("Purchase Order", po.name)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(doc, "Approve")

	def test_board_chair_cannot_create_purchase_order(self):
		frappe.set_user(self.board_chair_email)
		with self.assertRaises(frappe.ValidationError):
			make_purchase_order(self.project, amount=500, owner=self.board_chair_email)
