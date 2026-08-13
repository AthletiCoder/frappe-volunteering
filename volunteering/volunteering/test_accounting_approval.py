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
	get_or_create_department,
	get_or_create_employee,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	make_expense_claim,
	mute_accounting_test_emails,
	set_employee_grade,
)
from volunteering.volunteering.approval_routing import PENDING_APPROVAL, escalate_document


class IntegrationTestAccountingApproval(IntegrationTestCase):
	"""End-to-end grade + reports_to approval flow for Expense Claims.

	Chain: employee (Associate, approve 0) -> manager (Manager, approve 2000)
	-> director (Director, approve 25000), where the band is Employee.grade.
	The workflow fixture routes Draft -> Pending Approval, gated by
	`pending_approver`.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._email_patcher = mute_accounting_test_emails()
		# The workflow fixture only supports grade approval; pin the flag so
		# results don't depend on the live site's setting.
		cls._prev_grade_flag = frappe.db.get_single_value(
			"Volunteering Accounting Settings", "use_grade_approval"
		)
		frappe.db.set_single_value("Volunteering Accounting Settings", "use_grade_approval", 1)
		frappe.clear_cache(doctype="Volunteering Accounting Settings")
		setup_accounting_custom_fields()
		frappe.clear_cache(doctype="Expense Claim")
		reload_accounting_workflows()
		ensure_workflow_actions()

		cls.project = get_or_create_project_with_cost_center()
		cls.employee_email = get_or_create_user(
			"employee-acct@example.com", ["Employee"], "Employee User"
		)
		cls.manager_email = get_or_create_user(
			"manager-acct@example.com", ["Employee"], "Manager User"
		)
		cls.director_email = get_or_create_user(
			"director-acct@example.com", ["Employee"], "Director User"
		)
		# Authority comes from the grade below, not from a board role.
		cls.board_chair_email = get_or_create_user(
			"board-chair-acct@example.com",
			["Employee"],
			"Board Chair",
		)
		cls.department = get_or_create_department("Operations", cls.manager_email)
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		cls.manager_employee = get_or_create_employee(
			cls.manager_email, cls.department, "Manager Employee"
		)
		cls.director_employee = get_or_create_employee(
			cls.director_email, cls.department, "Director Employee"
		)
		cls.board_chair_employee = get_or_create_employee(
			cls.board_chair_email, cls.department, "Board Chair Employee"
		)

		set_employee_grade(cls.employee, "Associate", reports_to=cls.manager_employee)
		set_employee_grade(cls.manager_employee, "Manager", reports_to=cls.director_employee)
		set_employee_grade(cls.director_employee, "Director", reports_to=None)
		set_employee_grade(cls.board_chair_employee, "Board of Directors")

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
		frappe.db.delete(
			"Expense Claim",
			{
				"employee": [
					"in",
					[self.employee, self.manager_employee, self.director_employee],
				]
			},
		)
		super().tearDown()

	def _submit_claim_as(self, user, amount=1500, employee=None, vendor_reason=None):
		employee = employee or self.employee
		frappe.set_user(user)
		claim = make_expense_claim(employee, self.project, amount=amount, owner=user)
		claim = frappe.get_doc("Expense Claim", claim.name)
		if vendor_reason:
			claim.vendor_override_reason = vendor_reason
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		return frappe.get_doc("Expense Claim", claim.name)

	def test_low_value_claim_routes_to_manager(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		self.assertEqual(claim.workflow_state, PENDING_APPROVAL)
		self.assertEqual(claim.pending_approver, self.manager_email)

	def test_manager_can_approve_low_value_claim(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.manager_email)
		approved = frappe.get_doc("Expense Claim", claim.name)
		apply_workflow(approved, "Approve")
		approved.reload()
		self.assertEqual(approved.workflow_state, "Approved")
		self.assertEqual(approved.docstatus, 1)

	def test_mid_value_claim_routes_past_manager_to_director(self):
		# 5000 exceeds Manager's 2000 approval authority; Director (25000) can.
		claim = self._submit_claim_as(self.employee_email, amount=5000)
		self.assertEqual(claim.workflow_state, PENDING_APPROVAL)
		self.assertEqual(claim.pending_approver, self.director_email)

	def test_high_value_claim_lands_with_first_manager(self):
		# 30000 exceeds everyone in the chain; the immediate manager receives
		# it and must escalate.
		claim = self._submit_claim_as(
			self.employee_email,
			amount=30000,
			vendor_reason="Vendor does not accept POs",
		)
		self.assertEqual(claim.workflow_state, PENDING_APPROVAL)
		self.assertEqual(claim.pending_approver, self.manager_email)

	def test_own_claim_skips_self_approval(self):
		# Manager's own claim must not route to themselves.
		claim = self._submit_claim_as(
			self.manager_email, amount=500, employee=self.manager_employee
		)
		self.assertEqual(claim.workflow_state, PENDING_APPROVAL)
		self.assertEqual(claim.pending_approver, self.director_email)

	def test_escalation_requires_reason(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.manager_email)
		with self.assertRaises(frappe.ValidationError):
			escalate_document("Expense Claim", claim.name, "")

	def test_escalation_blocked_when_limit_covers_amount(self):
		# Manager can approve 1500 outright, so Escalate is not allowed.
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.manager_email)
		with self.assertRaises(frappe.ValidationError):
			escalate_document("Expense Claim", claim.name, "Passing the buck")

	def test_escalation_moves_up_the_chain(self):
		claim = self._submit_claim_as(
			self.employee_email,
			amount=30000,
			vendor_reason="Vendor does not accept POs",
		)
		self.assertEqual(claim.pending_approver, self.manager_email)

		frappe.set_user(self.manager_email)
		escalate_document("Expense Claim", claim.name, "Amount above my grade limit")
		claim.reload()
		self.assertEqual(claim.workflow_state, PENDING_APPROVAL)
		self.assertEqual(claim.pending_approver, self.director_email)

	def test_rejected_claim_stays_rejected_until_resubmit(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.manager_email)
		rejected = frappe.get_doc("Expense Claim", claim.name)
		apply_workflow(rejected, "Reject")
		rejected.reload()
		self.assertEqual(rejected.workflow_state, "Rejected")

		frappe.set_user(self.employee_email)
		resubmit = frappe.get_doc("Expense Claim", rejected.name)
		apply_workflow(resubmit, "Re-submit")
		resubmit.reload()
		self.assertEqual(resubmit.workflow_state, PENDING_APPROVAL)

	def test_claim_without_receipt_cannot_submit(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=1500)
		frappe.db.delete("File", {"attached_to_name": claim.name})
		claim = frappe.get_doc("Expense Claim", claim.name)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(claim, "Submit")

	def test_board_of_directors_grade_cannot_create_expense_claim(self):
		frappe.set_user(self.board_chair_email)
		with self.assertRaises(frappe.ValidationError):
			make_expense_claim(
				self.board_chair_employee,
				self.project,
				amount=500,
				owner=self.board_chair_email,
			)
