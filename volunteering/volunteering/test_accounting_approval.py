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
	make_expense_claim,
)
from volunteering.volunteering.approval_routing import (
	PENDING_EXPENSE_TIER_1,
	PENDING_TIER_2,
	PENDING_TIER_3,
)


class IntegrationTestAccountingApproval(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.flags.mute_emails = True
		cls._email_patcher = patch("frappe.sendmail")
		cls._email_patcher.start()
		setup_accounting_custom_fields()
		frappe.clear_cache(doctype="Expense Claim")
		reload_accounting_workflows()
		ensure_workflow_actions()
		cls.project = get_or_create_project_with_cost_center()
		cls.dept_head_email = get_or_create_user(
			"dept-head-acct@example.com", ["Employee", "NGO Department Head"], "Dept Head"
		)
		cls.employee_email = get_or_create_user(
			"employee-acct@example.com", ["Employee"], "Employee User"
		)
		cls.board_member_email = get_or_create_user(
			"board-member-acct@example.com", ["Employee", "NGO Board Member"], "Board Member"
		)
		cls.board_chair_email = get_or_create_user(
			"board-chair-acct@example.com",
			["Employee", "NGO Board Chairperson"],
			"Board Chair",
		)
		cls.department = get_or_create_department("Operations", cls.dept_head_email)
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		cls.dept_head_employee = get_or_create_employee(
			cls.dept_head_email, cls.department, "Dept Head Employee"
		)
		cls.board_chair_employee = get_or_create_employee(
			cls.board_chair_email, cls.department, "Board Chair Employee"
		)

	@classmethod
	def tearDownClass(cls):
		cls._email_patcher.stop()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def tearDown(self):
		frappe.db.delete("Expense Claim", {"employee": ["in", [self.employee, self.dept_head_employee]]})
		super().tearDown()

	def _submit_claim_as(self, user, amount=1500, employee=None):
		employee = employee or self.employee
		frappe.set_user(user)
		claim = make_expense_claim(employee, self.project, amount=amount, owner=user)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		return frappe.get_doc("Expense Claim", claim.name)

	def test_low_value_claim_routes_to_department_head(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		self.assertEqual(claim.workflow_state, PENDING_EXPENSE_TIER_1)
		self.assertEqual(claim.expense_approver, self.dept_head_email)

	def test_department_head_can_approve_low_value_claim(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.dept_head_email)
		approved = frappe.get_doc("Expense Claim", claim.name)
		apply_workflow(approved, "Approve")
		approved.reload()
		self.assertEqual(approved.workflow_state, "Approved")
		self.assertEqual(approved.docstatus, 1)

	def test_mid_value_claim_routes_to_board_member(self):
		claim = self._submit_claim_as(self.employee_email, amount=5000)
		self.assertEqual(claim.workflow_state, PENDING_TIER_2)

	def test_high_value_claim_routes_to_board_chair(self):
		claim = self._submit_claim_as(self.employee_email, amount=15000)
		self.assertEqual(claim.workflow_state, PENDING_TIER_3)

	def test_dept_head_requester_routes_to_board_member(self):
		claim = self._submit_claim_as(self.dept_head_email, amount=500, employee=self.dept_head_employee)
		self.assertEqual(claim.workflow_state, PENDING_TIER_2)

	def test_escalation_requires_reason(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.dept_head_email)
		doc = frappe.get_doc("Expense Claim", claim.name)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(doc, "Escalate")

	def test_escalation_moves_to_board_member(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.dept_head_email)
		frappe.db.set_value(
			"Expense Claim",
			claim.name,
			"escalation_reason",
			"Need board visibility on vendor choice",
		)
		doc = frappe.get_doc("Expense Claim", claim.name)
		apply_workflow(doc, "Escalate")
		doc.reload()
		self.assertEqual(doc.workflow_state, PENDING_TIER_2)

	def test_rejected_claim_stays_rejected_until_resubmit(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.dept_head_email)
		rejected = frappe.get_doc("Expense Claim", claim.name)
		apply_workflow(rejected, "Reject")
		rejected.reload()
		self.assertEqual(rejected.workflow_state, "Rejected")

		frappe.set_user(self.employee_email)
		resubmit = frappe.get_doc("Expense Claim", rejected.name)
		apply_workflow(resubmit, "Re-submit")
		resubmit.reload()
		self.assertEqual(resubmit.workflow_state, PENDING_EXPENSE_TIER_1)

	def test_claim_without_receipt_cannot_submit(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=1500)
		frappe.db.delete("File", {"attached_to_name": claim.name})
		claim = frappe.get_doc("Expense Claim", claim.name)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(claim, "Submit")

	def test_board_chair_cannot_create_expense_claim(self):
		frappe.set_user(self.board_chair_email)
		with self.assertRaises(frappe.ValidationError):
			make_expense_claim(
				self.board_chair_employee,
				self.project,
				amount=500,
				owner=self.board_chair_email,
			)
