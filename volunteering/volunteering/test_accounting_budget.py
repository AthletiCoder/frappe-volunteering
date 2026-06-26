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
	set_project_department_budget,
)
from volunteering.volunteering.budget_service import get_budget_health, get_consumed_amount


class IntegrationTestAccountingBudget(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.flags.mute_emails = True
		cls._email_patcher = patch("frappe.sendmail")
		cls._email_patcher.start()
		setup_accounting_custom_fields()
		reload_accounting_workflows()
		frappe.db.set_single_value("Volunteering Accounting Settings", "enable_budget_warnings", 1)

		cls.project = get_or_create_project_with_cost_center()
		cls.employee_email = get_or_create_user(
			"employee-acct@example.com", ["Employee"], "Employee User"
		)
		cls.department = get_or_create_department("Operations")
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		set_project_department_budget(cls.project, cls.department, 10000)

	@classmethod
	def tearDownClass(cls):
		cls._email_patcher.stop()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def tearDown(self):
		frappe.db.delete("Expense Claim", {"employee": self.employee})
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
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		self.assertTrue(frappe.db.exists("Expense Claim", claim.name))
