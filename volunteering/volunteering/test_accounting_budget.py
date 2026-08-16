# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from unittest.mock import patch

from volunteering.volunteering.accounting_setup import (
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
	set_project_department_budget,
)
from volunteering.volunteering.budget_service import get_budget_health, get_consumed_amount


class IntegrationTestAccountingBudget(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._email_patcher = mute_accounting_test_emails()
		cls._gs_patcher = patch("frappe.model.document.update_global_search")
		cls._gs_patcher.start()
		cls._gs_queue_patcher = patch("frappe.utils.global_search.sync_value_in_queue")
		cls._gs_queue_patcher.start()
		setup_accounting_custom_fields()
		reload_accounting_workflows()
		frappe.db.set_single_value("Volunteering Accounting Settings", "enable_budget_warnings", 1)

		cls.project = get_or_create_project_with_cost_center()
		cls.employee_email = get_or_create_user(
			"employee-acct@example.com", ["Employee"], "Employee User"
		)
		cls.manager_email = get_or_create_user(
			"budget-mgr-acct@example.com", ["Employee"], "Budget Mgr"
		)
		cls.department = get_or_create_department("Operations")
		cls.manager = get_or_create_employee(cls.manager_email, cls.department, "Budget Manager")
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		# Director grade approves up to 25000, enough for the 12000 over-budget claims.
		set_employee_grade(cls.manager, "Director")
		set_employee_grade(cls.employee, "Associate", reports_to=cls.manager)
		set_project_department_budget(cls.project, cls.department, 10000)

	@classmethod
	def tearDownClass(cls):
		cls._gs_queue_patcher.stop()
		cls._gs_patcher.stop()
		cls._email_patcher.close()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def tearDown(self):
		frappe.db.delete("Expense Claim", {"employee": self.employee})
		frappe.db.delete("Employee Advance", {"employee": self.employee})
		super().tearDown()

	def test_expense_claim_gets_department_from_employee(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=1500)
		self.assertEqual(claim.department, self.department)

	def test_submitted_claim_counts_toward_consumed_budget(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=2000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		consumed = get_consumed_amount(self.project, self.department)
		self.assertGreaterEqual(consumed, 2000)

	def test_budget_health_returns_project_department_row(self):
		frappe.set_user("Administrator")
		rows = get_budget_health(self.project)
		match = [row for row in rows if row["department"] == self.department]
		self.assertEqual(len(match), 1)
		self.assertEqual(match[0]["allocated"], 10000)

	def test_over_budget_claim_still_saves_with_soft_warning(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=12000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.vendor_override_reason = "Urgent reimbursement; PO not feasible."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		self.assertTrue(frappe.db.exists("Expense Claim", claim.name))
		self.assertEqual(frappe.db.get_value("Expense Claim", claim.name, "workflow_state"), "Pending Approval")

	def test_approve_over_budget_requires_exceedance_reason(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=12000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.vendor_override_reason = "Urgent reimbursement; PO not feasible."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		claim.reload()
		self.assertEqual(claim.pending_approver, self.manager_email)

		frappe.set_user(self.manager_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(claim, "Approve")

	def test_approve_over_budget_with_reason_under_hard_limit(self):
		# 20% over 10000 = 12000 → under 25% hard block
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=12000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.vendor_override_reason = "Urgent reimbursement; PO not feasible."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		claim.reload()
		self.assertEqual(claim.pending_approver, self.manager_email)

		frappe.set_user(self.manager_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.budget_override_reason = "Seasonal campaign overspend approved by dept."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Approve")
		claim.reload()
		self.assertEqual(claim.workflow_state, "Approved")

	def test_form_has_approval_tab_and_budget_exceedance_label(self):
		meta = frappe.get_meta("Expense Claim")
		self.assertTrue(meta.has_field("approval_routing_tab"))
		self.assertTrue(meta.has_field("budget_override_reason"))
		df = meta.get_field("budget_override_reason")
		self.assertEqual(df.label, "Budget Exceedance Reason")

		project_meta = frappe.get_meta("Project")
		self.assertFalse(bool(project_meta.get_field("fund_project_type")))
		self.assertTrue(project_meta.has_field("parent_campaign"))

	def test_employee_advance_does_not_consume_project_budget(self):
		before = get_consumed_amount(self.project, self.department)
		frappe.set_user(self.employee_email)
		company = frappe.db.get_value("Employee", self.employee, "company")
		advance = frappe.get_doc(
			{
				"doctype": "Employee Advance",
				"employee": self.employee,
				"company": company,
				"purpose": "Budget isolation",
				"advance_amount": 1500,
				"posting_date": frappe.utils.nowdate(),
			}
		)
		advance.insert(ignore_permissions=True)
		apply_workflow(advance, "Submit")
		self.assertFalse(advance.project)
		self.assertEqual(get_consumed_amount(self.project, self.department), before)

	def test_expense_claim_requires_project(self):
		frappe.set_user(self.employee_email)
		with self.assertRaises(frappe.ValidationError):
			make_expense_claim(self.employee, None, amount=500)
