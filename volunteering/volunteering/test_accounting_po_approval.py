# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.accounting_setup import (
	ensure_workflow_actions,
	reload_accounting_workflows,
	setup_accounting_custom_fields,
)
from volunteering.volunteering.accounting_test_utils import (
	delete_documents_with_workflow_actions,
	get_or_create_department,
	get_or_create_employee,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	make_purchase_order,
	mute_accounting_test_emails,
	set_employee_grade,
)
from volunteering.volunteering.approval_routing import (
	PENDING_APPROVAL,
	escalate_document,
	get_fallback_board_approver,
)


class IntegrationTestAccountingPOApproval(IntegrationTestCase):
	"""Grade + reports_to approval flow for Purchase Orders.

	Chain: employee (Associate, approve 0) -> manager (Manager, approve 2000)
	-> director (Director, approve 25000). The workflow fixture routes
	Draft -> Pending Approval and gates Approve on `pending_approver`.

	Every user needs `Purchase User`: ERPNext's own party/account validation
	runs before the volunteering hooks and would otherwise raise PermissionError.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._email_patcher = mute_accounting_test_emails()
		cls._prev_grade_flag = frappe.db.get_single_value(
			"Volunteering Accounting Settings", "use_grade_approval"
		)
		frappe.db.set_single_value("Volunteering Accounting Settings", "use_grade_approval", 1)
		frappe.clear_cache(doctype="Volunteering Accounting Settings")
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
		cls.manager_email = get_or_create_user(
			"manager-acct@example.com",
			["Employee", "Purchase User"],
			"Manager User",
		)
		cls.director_email = get_or_create_user(
			"director-acct@example.com",
			["Employee", "Purchase User"],
			"Director User",
		)
		# Authority comes from the Board of Directors grade, not a board role.
		cls.board_email = get_or_create_user(
			"board-chair-po@example.com",
			["Employee", "Purchase User"],
			"Board PO",
		)
		cls.department = get_or_create_department("Operations")
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		cls.manager_employee = get_or_create_employee(
			cls.manager_email, cls.department, "Manager Employee"
		)
		cls.director_employee = get_or_create_employee(
			cls.director_email, cls.department, "Director Employee"
		)
		cls.board_employee = get_or_create_employee(
			cls.board_email, cls.department, "Board PO Employee"
		)

		cls.unmanaged_email = get_or_create_user(
			"po-unmanaged@example.com", ["Employee", "Purchase User"], "PO Unmanaged"
		)
		cls.unmanaged_employee = get_or_create_employee(
			cls.unmanaged_email, cls.department, "PO Unmanaged Employee"
		)

		set_employee_grade(cls.employee, "Associate", reports_to=cls.manager_employee)
		set_employee_grade(cls.manager_employee, "Manager", reports_to=cls.director_employee)
		set_employee_grade(cls.director_employee, "Director", reports_to=None)
		set_employee_grade(cls.board_employee, "Board of Directors")
		set_employee_grade(cls.unmanaged_employee, "Associate", reports_to=None)

	@classmethod
	def tearDownClass(cls):
		cls._email_patcher.close()
		frappe.flags.mute_emails = False
		frappe.db.set_single_value(
			"Volunteering Accounting Settings",
			"use_grade_approval",
			1 if cls._prev_grade_flag is None else cls._prev_grade_flag,
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
		po = self._submit_po_as(self.employee_email, amount=1500)
		self.assertEqual(po.workflow_state, PENDING_APPROVAL)
		self.assertEqual(po.pending_approver, self.manager_email)

	def test_mid_value_po_routes_past_manager_to_director(self):
		po = self._submit_po_as(self.employee_email, amount=5000)
		self.assertEqual(po.pending_approver, self.director_email)

	def test_high_value_po_lands_with_first_manager(self):
		po = self._submit_po_as(self.employee_email, amount=30000)
		self.assertEqual(po.pending_approver, self.manager_email)

	def test_manager_can_approve_low_value_po(self):
		po = self._submit_po_as(self.employee_email, amount=1500)
		frappe.set_user(self.manager_email)
		approved = frappe.get_doc("Purchase Order", po.name)
		apply_workflow(approved, "Approve")
		approved.reload()
		self.assertEqual(approved.workflow_state, "Approved")
		self.assertEqual(approved.docstatus, 1)

	def test_escalation_moves_up_the_chain(self):
		po = self._submit_po_as(self.employee_email, amount=30000)
		frappe.set_user(self.manager_email)
		escalate_document("Purchase Order", po.name, "Amount above my grade limit")
		po.reload()
		self.assertEqual(po.workflow_state, PENDING_APPROVAL)
		self.assertEqual(po.pending_approver, self.director_email)

	def test_po_without_reporting_chain_falls_back_to_board(self):
		po = self._submit_po_as(self.unmanaged_email, amount=1500)
		self.assertEqual(po.workflow_state, PENDING_APPROVAL)
		self.assertNotEqual(po.pending_approver, self.unmanaged_email)
		self.assertEqual(po.pending_approver, get_fallback_board_approver())

	def test_manager_cannot_approve_beyond_grade_limit(self):
		po = self._submit_po_as(self.employee_email, amount=30000)
		frappe.set_user(self.manager_email)
		doc = frappe.get_doc("Purchase Order", po.name)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(doc, "Approve")

	def test_board_of_directors_grade_cannot_create_purchase_order(self):
		frappe.set_user(self.board_email)
		with self.assertRaises(frappe.ValidationError):
			make_purchase_order(self.project, amount=500, owner=self.board_email)
