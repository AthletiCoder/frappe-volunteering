# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from unittest.mock import patch

from volunteering.volunteering.accounting_dashboard.pending_approvals import get_pending_approvals
from volunteering.volunteering.accounting_dashboard.pending_payments import (
	get_pending_reimbursements,
	get_pending_vendor_payments,
)
from volunteering.volunteering.accounting_dashboard.setup import (
	ensure_accounting_pages,
	send_weekly_pending_approval_reminder,
)
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
	make_expense_claim,
)
from volunteering.volunteering.expense_claim_permissions import (
	get_permission_query_conditions,
	has_permission,
)


class IntegrationTestAccountingDashboard(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.flags.mute_emails = True
		cls._email_patcher = patch("frappe.sendmail")
		cls._email_patcher.start()
		cls._gs_patcher = patch("frappe.model.document.update_global_search")
		cls._gs_patcher.start()
		cls._gs_queue_patcher = patch("frappe.utils.global_search.sync_value_in_queue")
		cls._gs_queue_patcher.start()
		# Approval routing follows the reports_to chain; pin the flag so results
		# don't depend on the live site's setting.
		cls._prev_designation_flag = frappe.db.get_single_value(
			"Volunteering Accounting Settings", "use_designation_approval"
		)
		frappe.db.set_single_value(
			"Volunteering Accounting Settings", "use_designation_approval", 1
		)
		frappe.clear_cache(doctype="Volunteering Accounting Settings")
		setup_accounting_custom_fields()
		frappe.clear_cache(doctype="Expense Claim")
		reload_accounting_workflows()
		ensure_workflow_actions()
		ensure_accounting_pages()

		ensure_designations("Associate", "Manager")

		cls.project = get_or_create_project_with_cost_center()
		cls.dept_head_email = get_or_create_user(
			"dept-head-acct@example.com", ["Employee", "NGO Department Head"], "Dept Head"
		)
		cls.other_dept_head_email = get_or_create_user(
			"other-dept-head-acct@example.com", ["Employee", "NGO Department Head"], "Other Head"
		)
		cls.employee_email = get_or_create_user(
			"employee-acct@example.com", ["Employee"], "Employee User"
		)
		cls.accounts_email = get_or_create_user(
			"accounts-acct@example.com", ["Employee", "Accounts User"], "Accounts User"
		)
		cls.other_employee_email = get_or_create_user(
			"other-employee-acct@example.com", ["Employee"], "Other Employee"
		)
		cls.department = get_or_create_department("Operations", cls.dept_head_email)
		cls.other_department = get_or_create_department("HR", cls.other_dept_head_email)
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		cls.other_employee = get_or_create_employee(
			cls.other_employee_email, cls.other_department, "Other Employee"
		)
		cls.dept_head_employee = get_or_create_employee(
			cls.dept_head_email, cls.department, "Dept Head Employee"
		)

		# The department head only becomes the approver by sitting on the
		# employee's reports_to chain with a designation limit covering the claim.
		frappe.db.set_value(
			"Employee",
			cls.dept_head_employee,
			{"designation": "Manager", "reports_to": None},
		)
		frappe.db.set_value(
			"Employee",
			cls.employee,
			{"designation": "Associate", "reports_to": cls.dept_head_employee},
		)

	@classmethod
	def tearDownClass(cls):
		cls._gs_queue_patcher.stop()
		cls._gs_patcher.stop()
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
		delete_documents_with_workflow_actions(
			"Expense Claim",
			{"employee": ["in", [self.employee, self.other_employee]]},
		)
		super().tearDown()

	def _submit_claim_as(self, user, amount=1500, employee=None):
		employee = employee or self.employee
		frappe.set_user(user)
		claim = make_expense_claim(employee, self.project, amount=amount, owner=user)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		return frappe.get_doc("Expense Claim", claim.name)

	def _approve_claim(self, claim):
		frappe.set_user(self.dept_head_email)
		doc = frappe.get_doc("Expense Claim", claim.name)
		apply_workflow(doc, "Approve")
		doc.reload()
		return doc

	def test_permission_hooks_are_importable(self):
		from volunteering import hooks

		self.assertTrue(
			callable(frappe.get_attr(hooks.permission_query_conditions["Expense Claim"]))
		)
		self.assertTrue(callable(frappe.get_attr(hooks.has_permission["Expense Claim"])))

	def test_dept_head_permission_query_scopes_to_department(self):
		condition = get_permission_query_conditions(self.dept_head_email)
		self.assertIn(self.employee, condition)
		self.assertNotIn(self.other_employee, condition)

	def test_dept_head_cannot_read_other_department_claim(self):
		claim = self._submit_claim_as(
			self.other_employee_email, amount=1500, employee=self.other_employee
		)
		doc = frappe.get_doc("Expense Claim", claim.name)
		self.assertFalse(has_permission(doc, "read", self.dept_head_email))

	def test_dept_head_can_read_own_department_claim(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		doc = frappe.get_doc("Expense Claim", claim.name)
		self.assertTrue(has_permission(doc, "read", self.dept_head_email))

	def test_get_pending_approvals_for_department_head(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.dept_head_email)
		rows = get_pending_approvals()
		names = {row.reference_name for row in rows}
		self.assertIn(claim.name, names)
		match = next(row for row in rows if row.reference_name == claim.name)
		self.assertIn("Approve", match.available_actions)

	def test_get_pending_reimbursements_requires_accounts_role(self):
		frappe.set_user(self.employee_email)
		with self.assertRaises(frappe.PermissionError):
			get_pending_reimbursements()

	def test_get_pending_reimbursements_lists_approved_unpaid_claims(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		approved = self._approve_claim(claim)
		self.assertEqual(approved.approval_status, "Approved")
		self.assertEqual(approved.status, "Unpaid")

		frappe.set_user(self.accounts_email)
		rows = get_pending_reimbursements()
		names = {row.name for row in rows}
		self.assertIn(approved.name, names)

	def test_get_pending_vendor_payments_requires_accounts_role(self):
		frappe.set_user(self.employee_email)
		with self.assertRaises(frappe.PermissionError):
			get_pending_vendor_payments()

	def test_ensure_accounting_pages_is_idempotent(self):
		ensure_accounting_pages()
		self.assertFalse(frappe.db.exists("Page", "project-budget-health"))
		self.assertFalse(frappe.db.exists("Page", "advance-portal"))
		for retired in (
			"pending-my-approval",
			"pending-reimburse",
			"pending-vendor-pay",
			"project-budget-health",
			"advance-portal",
		):
			self.assertFalse(frappe.db.exists("Page", retired))

		ensure_accounting_pages()
		self.assertTrue(
			frappe.db.exists("Workspace", "My Expenses")
			or frappe.db.get_value("Workspace", {"label": "My Expenses"}, "name")
		)
		self.assertTrue(frappe.db.exists("Workspace Sidebar", "My Expenses"))
		sidebar = frappe.get_doc("Workspace Sidebar", "My Expenses")
		# Shell only — workspace home link, no duplicated DocType nav
		labels = [item.label for item in sidebar.items if item.type == "Link"]
		self.assertEqual(labels, ["My Expenses"])
		self.assertFalse(
			{
				"My Expense Claims",
				"Claims to Reimburse",
				"Advance Portal",
				"Budget Health",
			}
			& set(labels)
		)

		ws = frappe.get_doc(
			"Workspace",
			frappe.db.exists("Workspace", "My Expenses")
			or frappe.db.get_value("Workspace", {"label": "My Expenses"}, "name"),
		)
		shortcut_labels = {s.label for s in ws.shortcuts}
		self.assertIn("Advance Portal", shortcut_labels)
		self.assertIn("Budget Health", shortcut_labels)
		self.assertTrue(
			{
				"Expense Claims Pending Me",
				"Claims to Reimburse",
				"Vendor Invoices to Pay",
			}
			<= shortcut_labels
		)
		advance = next(s for s in ws.shortcuts if s.label == "Advance Portal")
		self.assertEqual(advance.type, "URL")
		self.assertEqual(advance.url, "/volunteering/advances")
		budget = next(s for s in ws.shortcuts if s.label == "Budget Health")
		self.assertEqual(budget.type, "URL")
		self.assertEqual(budget.url, "/volunteering/budget-health")

		if frappe.db.exists("Workspace Sidebar", "Volunteering"):
			vol_sidebar = frappe.get_doc("Workspace Sidebar", "Volunteering")
			vol_sections = {
				item.label
				for item in vol_sidebar.items
				if item.type == "Section Break"
				and item.label in ("Pending Approvals", "Approvals", "Accounts Ops", "Budgets")
			}
			self.assertEqual(vol_sections, set())

	@patch("volunteering.volunteering.accounting_dashboard.setup._send_reminder_email")
	def test_weekly_reminder_targets_users_with_pending_approvals(self, mock_send):
		self._submit_claim_as(self.employee_email, amount=1500)
		send_weekly_pending_approval_reminder()
		called_users = {call.args[0] for call in mock_send.call_args_list}
		self.assertIn(self.dept_head_email, called_users)
