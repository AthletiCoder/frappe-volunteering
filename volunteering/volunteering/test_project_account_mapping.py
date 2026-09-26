"""Approval, least-privilege mapping, category ceilings and upgrade regressions."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department,
	get_or_create_employee,
	get_or_create_expense_account,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	mute_accounting_test_emails,
)
from volunteering.volunteering.budget_service import _budget_violations, get_account_allocated_budget
from volunteering.volunteering.project_account_mapping import (
	backfill_budget_labels,
	get_mapping_workspace,
	save_account_mapping,
)
from volunteering.volunteering.project_expense_accounts import (
	assign_and_validate_project_expense_accounts,
	employee_options,
)
from volunteering.volunteering.project_proposals import review_proposal, save_proposal, submit_proposal
from volunteering.volunteering.project_workspace import get_project, get_setup_options


class IntegrationTestProjectAccountMapping(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.emails = mute_accounting_test_emails()
		base = frappe.get_doc("Project", get_or_create_project_with_cost_center())
		cls.company, cls.centre = base.company, base.cost_center
		cls.account = get_or_create_expense_account(cls.company)
		cls.proposer = get_or_create_user("label-proposer@example.com", ["Employee", "Project Proposer"])
		cls.manager = get_or_create_user("label-manager@example.com", ["Employee", "Projects Manager"])
		cls.accounts = get_or_create_user("label-accounts-manager@example.com", ["Accounts Manager"])
		cls.accounts_user = get_or_create_user("label-accounts-user@example.com", ["Accounts User"])
		department = get_or_create_department("Label Mapping Tests")
		with patch("volunteering.volunteering.leave_setup.assign_leave_policy_to_employee"):
			for user in (cls.proposer, cls.manager, cls.accounts, cls.accounts_user):
				get_or_create_employee(user, department)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		cls.emails.close()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user(self.proposer)
		self.data = {
			"project_name": "Label budgets " + frappe.generate_hash(length=8),
			"project_purpose": "Test separate label approval and ledger classification",
			"project_owner": self.proposer,
			"participants": [{"user": self.proposer, "access_level": "Financial"}],
			"operational_status": "Active",
			"cost_center": self.centre,
			"project_budget_control": "Strict",
			"total_approved_budget": 1000,
			"account_budget_control": "Strict",
			"account_budgets": [
				{"employee_label": "Travel", "approved_amount": 100, "is_active": 1},
				{"employee_label": "Materials", "approved_amount": 600, "is_active": 1},
			],
		}
		self.proposal = save_proposal(self.data, assigned_approver=self.manager)
		self.proposal = submit_proposal(self.proposal["name"], self.proposal["modified"])
		frappe.set_user(self.manager)
		approved = review_proposal(self.proposal["name"], "approve", self.proposal["modified"])
		self.project = approved["project"]

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _map(self):
		frappe.set_user(self.accounts)
		workspace = get_mapping_workspace(self.project)["project"]
		return save_account_mapping(
			self.project,
			workspace["modified"],
			[
				{"budget_key": row["budget_key"], "expense_accounts": [self.account]}
				for row in workspace["rows"]
			],
		)

	def _claim(self, amount=125):
		project = frappe.get_doc("Project", self.project)
		return frappe.get_doc(
			{
				"doctype": "Expense Claim",
				"company": self.company,
				"project": self.project,
				"workflow_state": "Pending Receipt Review",
				"expenses": [
					{
						"project_expense_account": project.account_budgets[0].budget_key,
						"amount": amount,
						"sanctioned_amount": amount,
					}
				],
			}
		)

	def test_project_approves_without_accounts_and_employee_choices_remain_available(self):
		doc = frappe.get_doc("Project", self.project)
		self.assertTrue(all(not row.expense_account for row in doc.account_budgets))
		self.assertEqual(
			[row["label"] for row in employee_options(doc)],
			["Travel", "Materials", "Others"],
		)
		claim = self._claim()
		assign_and_validate_project_expense_accounts(claim)
		self.assertEqual(
			frappe.db.get_value("Account", claim.expenses[0].default_account, "account_name"),
			"Unclassified Employee Expenses",
		)

	def test_only_accounts_manager_can_access_mapping(self):
		for user in (self.proposer, self.manager, self.accounts_user, "Guest"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				get_mapping_workspace(self.project)
			with self.assertRaises(frappe.PermissionError):
				save_account_mapping(self.project, "forged", [])

	def test_mapping_preserves_approved_budgets_and_logs_actor(self):
		result = self._map()
		self.assertTrue(result["ready"])
		self.assertEqual([row["approved_amount"] for row in result["rows"]], [100, 600, 300])
		self.assertEqual(get_account_allocated_budget(self.project, self.account), 1000)
		log = frappe.get_all(
			"Project Budget Revision",
			filters={"project": self.project, "reason": "Expense label ledger mapping (Accounts Manager)"},
			fields=["changed_by", "after_values"],
		)
		self.assertEqual(log[0].changed_by, self.accounts)
		self.assertIn("ledger_mappings", json.loads(log[0].after_values))

	def test_employee_choices_are_labels_only_and_resolve_hidden_account(self):
		self._map()
		frappe.set_user(self.proposer)
		choices = employee_options(frappe.get_doc("Project", self.project))
		self.assertEqual([row["label"] for row in choices], ["Travel", "Materials", "Others"])
		self.assertNotIn(self.account, json.dumps(choices))
		self.assertNotIn("expense_accounts", get_setup_options(self.project))
		self.assertNotIn("expense_account", get_project(self.project)["account_budgets"][0])
		claim = self._claim()
		assign_and_validate_project_expense_accounts(claim)
		self.assertEqual(claim.expenses[0].default_account, self.account)
		claim.expenses[0].project_expense_account = self.account
		with self.assertRaises(frappe.ValidationError):
			assign_and_validate_project_expense_accounts(claim)

	def test_shared_ledger_does_not_merge_label_ceilings(self):
		self._map()
		claim = self._claim(125)
		assign_and_validate_project_expense_accounts(claim)
		with (
			patch("volunteering.volunteering.budget_service.get_consumed_amount", return_value=0),
			patch("volunteering.volunteering.budget_service.get_project_label_consumption", return_value={}),
			patch(
				"volunteering.volunteering.budget_service.get_project_account_consumption", return_value={}
			),
		):
			violations = _budget_violations(claim, frappe.get_doc("Project", self.project), None)
		self.assertEqual(len(violations), 1)
		self.assertIn("Travel", violations[0].message)
		self.assertEqual(violations[0].mode, "Strict")

	def test_mapping_rejects_budget_injection_incomplete_and_stale_payloads(self):
		frappe.set_user(self.accounts)
		project = get_mapping_workspace(self.project)["project"]
		rows = [
			{"budget_key": row["budget_key"], "expense_accounts": [self.account]}
			for row in project["rows"]
		]
		with self.assertRaises(frappe.TimestampMismatchError):
			save_account_mapping(self.project, "stale", rows)
		with self.assertRaises(frappe.ValidationError):
			save_account_mapping(self.project, project["modified"], rows[:1])
		rows[0]["approved_amount"] = 99999
		with self.assertRaises(frappe.ValidationError):
			save_account_mapping(self.project, project["modified"], rows)

	def test_invalid_ledger_and_direct_desk_mutation_are_rejected(self):
		frappe.set_user(self.accounts)
		project = get_mapping_workspace(self.project)["project"]
		invalid = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Asset", "is_group": 0}, "name"
		)
		with self.assertRaises(frappe.ValidationError):
			save_account_mapping(
				self.project,
				project["modified"],
				[
					{"budget_key": row["budget_key"], "expense_accounts": [invalid]}
					for row in project["rows"]
				],
			)
		doc = frappe.get_doc("Project", self.project)
		doc.account_budgets[0].expense_account = self.account
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_proposal_cannot_assign_ledger_accounts(self):
		frappe.set_user(self.proposer)
		data = {
			"account_budgets": [
				{
					"employee_label": "Injected",
					"expense_account": self.account,
					"approved_amount": 300,
					"is_active": 1,
				}
			]
		}
		with self.assertRaises(frappe.ValidationError):
			save_proposal(data, project=self.project, reason="Not allowed")

	def test_budget_revision_retains_mapping_and_new_unmapped_label_is_usable(self):
		self._map()
		frappe.set_user(self.proposer)
		rows = get_project(self.project)["account_budgets"]
		rows[0]["approved_amount"] = 200
		rows.append({"employee_label": "Meals", "approved_amount": 100, "is_active": 1})
		proposal = save_proposal(
			{"account_budgets": rows},
			project=self.project,
			reason="Add a category",
			assigned_approver=self.manager,
		)
		proposal = submit_proposal(proposal["name"], proposal["modified"])
		frappe.set_user(self.manager)
		review_proposal(proposal["name"], "approve", proposal["modified"])
		doc = frappe.get_doc("Project", self.project)
		self.assertEqual(doc.account_budgets[0].expense_account, self.account)
		meals = next(row for row in doc.account_budgets if row.employee_label == "Meals")
		self.assertFalse(meals.expense_account)
		self.assertEqual(
			{row["label"] for row in employee_options(doc)},
			{"Travel", "Materials", "Meals", "Others"},
		)

	def test_used_mapping_remains_an_editable_suggestion(self):
		self._map()
		project = get_mapping_workspace(self.project)["project"]
		rows = [
			{"budget_key": row["budget_key"], "expense_accounts": row["expense_accounts"]}
			for row in project["rows"]
		]
		rows[0]["expense_accounts"] = []
		with patch("volunteering.volunteering.project_account_mapping.label_has_claims", return_value=True):
			result = save_account_mapping(self.project, project["modified"], rows)
		self.assertFalse(result["rows"][0]["expense_accounts"])

	def test_mapping_requires_an_approved_project_and_closed_projects_are_locked(self):
		frappe.set_user(self.accounts)
		with patch("volunteering.volunteering.project_account_mapping.is_approved", return_value=False):
			with self.assertRaisesRegex(frappe.ValidationError, "must approve"):
				get_mapping_workspace(self.project)
		frappe.db.set_value("Project", self.project, "budget_status", "Closed")
		with self.assertRaisesRegex(frappe.ValidationError, "Closed or archived"):
			save_account_mapping(self.project, str(frappe.get_doc("Project", self.project).modified), [])

	def test_backfill_is_idempotent_and_keeps_ledger_values(self):
		self._map()
		before = frappe.get_doc("Project", self.project)
		backfill_budget_labels()
		backfill_budget_labels()
		after = frappe.get_doc("Project", self.project)
		self.assertEqual(
			[r.budget_key for r in before.account_budgets], [r.budget_key for r in after.account_budgets]
		)
		self.assertEqual(
			[r.expense_account for r in before.account_budgets],
			[r.expense_account for r in after.account_budgets],
		)
