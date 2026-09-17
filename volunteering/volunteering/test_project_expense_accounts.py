# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.accounting_setup import (
	backfill_project_expense_accounts,
	ensure_expense_claim_field_visibility,
	setup_accounting_custom_fields,
)
from volunteering.volunteering.accounting_test_utils import (
	allow_project_expense_account,
	get_or_create_department,
	get_or_create_employee,
	get_or_create_expense_account,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	make_expense_claim,
	mute_accounting_test_emails,
	save_test_project,
	set_project_budget,
)
from volunteering.volunteering.project_expense_accounts import (
	get_project_expense_account_options,
)


class IntegrationTestProjectExpenseAccounts(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._email_patcher = mute_accounting_test_emails()
		setup_accounting_custom_fields()
		ensure_expense_claim_field_visibility()
		cls.project = get_or_create_project_with_cost_center()
		cls.employee_email = get_or_create_user(
			"project-account-employee@example.com", ["Employee"], "Project Account Employee"
		)
		cls.department = get_or_create_department("Operations")
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		cls.company = frappe.db.get_value("Employee", cls.employee, "company")
		cls.allowed_account = get_or_create_expense_account(cls.company)

	@classmethod
	def tearDownClass(cls):
		cls._email_patcher.close()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		set_project_budget(
			self.project,
			10000,
			project_control="No Control",
			account_control="No Control",
			account_budgets=[(self.allowed_account, 0)],
		)
		allow_project_expense_account(self.project, self.allowed_account, label="Employee-friendly expense")
		project = frappe.get_doc("Project", self.project)
		project.project_setup_version = 1
		project.project_purpose = project.project_purpose or "Expense-account fixture"
		project.project_owner = project.project_owner or self.employee_email
		project.operational_status = project.operational_status or "Active"
		if self.employee_email not in [row.user for row in project.project_participants]:
			project.append("project_participants", {"user": self.employee_email, "access_level": "Basic"})
		save_test_project(project)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Expense Claim", {"employee": self.employee})
		super().tearDown()

	def test_employee_receives_only_safe_project_options(self):
		frappe.set_user(self.employee_email)
		self.assertFalse(frappe.has_permission("Account", "read", user=self.employee_email))
		self.assertFalse(frappe.has_permission("Expense Claim Type", "read", user=self.employee_email))
		options = get_project_expense_account_options(self.project, self.company)
		self.assertEqual([row["value"] for row in options], [self.allowed_account])
		self.assertIn("Employee-friendly expense", options[0]["label"])
		self.assertNotIn("approved_amount", options[0])
		self.assertNotIn("balance", options[0])

	def test_selected_project_account_populates_hidden_gl_account(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=500)
		row = claim.expenses[0]
		self.assertEqual(row.project_expense_account, self.allowed_account)
		self.assertEqual(row.default_account, self.allowed_account)

	def test_typed_unlinked_account_is_rejected_server_side(self):
		unlinked = frappe.db.get_value(
			"Account",
			{
				"company": self.company,
				"root_type": "Expense",
				"is_group": 0,
				"disabled": 0,
				"name": ["!=", self.allowed_account],
			},
			"name",
		)
		if not unlinked:
			self.skipTest("The test company has only one leaf Expense Account")
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=500)
		claim.expenses[0].project_expense_account = unlinked
		with self.assertRaisesRegex(frappe.ValidationError, "not available for Project"):
			claim.save(ignore_permissions=True)

	def test_inactive_project_account_is_not_offered_or_accepted(self):
		frappe.set_user("Administrator")
		project = frappe.get_doc("Project", self.project)
		row = next(row for row in project.account_budgets if row.expense_account == self.allowed_account)
		row.is_active = 0
		save_test_project(project)

		frappe.set_user(self.employee_email)
		self.assertEqual(get_project_expense_account_options(self.project, self.company), [])
		with self.assertRaisesRegex(frappe.ValidationError, "no Expense Accounts available"):
			make_expense_claim(
				self.employee,
				self.project,
				amount=500,
				ensure_project_account=False,
			)

	def test_normal_migrate_does_not_repopulate_intentionally_empty_project(self):
		project = frappe.get_doc("Project", self.project)
		project.account_budgets = []
		save_test_project(project)

		backfill_project_expense_accounts()

		self.assertFalse(
			frappe.db.exists(
				"Project Account Budget",
				{
					"parent": self.project,
					"parenttype": "Project",
					"parentfield": "account_budgets",
				},
			)
		)
