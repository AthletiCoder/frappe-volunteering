# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.accounting_setup import (
	ensure_accounting_roles,
	ensure_receipt_reviewer_permissions,
	reload_accounting_workflows,
	setup_accounting_custom_fields,
)
from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department,
	get_or_create_employee,
	get_or_create_expense_claim_type,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	make_expense_claim,
	mute_accounting_test_emails,
	set_employee_grade,
	set_project_budget,
)
from volunteering.volunteering.approval_routing import get_approver_action_flags
from volunteering.volunteering.budget_service import (
	get_account_consumed_amount,
	get_budget_commitment_breakdown,
	get_budget_health,
	get_consumed_amount,
)
from volunteering.volunteering.receipt_review import review_receipts


class UnitTestBudgetCommitmentBreakdown(UnitTestCase):
	@patch("volunteering.volunteering.budget_service.get_project_total_allocated", return_value=10000)
	@patch("volunteering.volunteering.budget_service._active_budget_documents")
	@patch("volunteering.volunteering.budget_service.frappe.get_doc")
	def test_separates_pending_claims_approved_expenditure_and_purchase_orders(
		self, get_doc, active_documents, _allocated
	):
		documents = {
			("Expense Claim", "PENDING"): frappe._dict(
				doctype="Expense Claim",
				workflow_state="Pending Receipt Review",
				expenses=[frappe._dict(default_account="Expense", amount=300)],
			),
			("Expense Claim", "APPROVED"): frappe._dict(
				doctype="Expense Claim",
				workflow_state="Approved",
				expenses=[frappe._dict(default_account="Expense", amount=300, sanctioned_amount=250)],
			),
			("Purchase Order", "PO"): frappe._dict(
				doctype="Purchase Order",
				workflow_state="Approved",
				items=[frappe._dict(expense_account="Expense", amount=400)],
			),
		}
		active_documents.side_effect = lambda doctype, _project: {
			"Expense Claim": [
				frappe._dict(name="PENDING", workflow_state="Pending Receipt Review"),
				frappe._dict(name="APPROVED", workflow_state="Approved"),
			],
			"Purchase Order": [frappe._dict(name="PO", workflow_state="Approved")],
		}[doctype]
		get_doc.side_effect = lambda doctype, name: documents[(doctype, name)]

		status = get_budget_commitment_breakdown("PROJECT")
		self.assertEqual(status["pending_claim_commitments"], 300)
		self.assertEqual(status["purchase_order_commitments"], 400)
		self.assertEqual(status["pending_commitments"], 700)
		self.assertEqual(status["approved_expenditure"], 250)
		self.assertEqual(status["total_committed"], 950)
		self.assertEqual(status["available_after_commitments"], 9050)


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
		ensure_accounting_roles()
		ensure_receipt_reviewer_permissions()
		reload_accounting_workflows()
		frappe.db.set_single_value("Volunteering Accounting Settings", "enable_budget_warnings", 1)

		cls.project = get_or_create_project_with_cost_center()
		cls.employee_email = get_or_create_user("employee-acct@example.com", ["Employee"], "Employee User")
		cls.manager_email = get_or_create_user("budget-mgr-acct@example.com", ["Employee"], "Budget Mgr")
		cls.reviewer_email = get_or_create_user(
			"budget-receipt-reviewer@example.com",
			["Expense Receipt Reviewer"],
			"Budget Receipt Reviewer",
		)
		cls.department = get_or_create_department("Operations")
		cls.manager = get_or_create_employee(cls.manager_email, cls.department, "Budget Manager")
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		# Director grade approves up to 25000, enough for the 12000 over-budget claims.
		set_employee_grade(cls.manager, "Director")
		set_employee_grade(cls.employee, "Associate", reports_to=cls.manager)
		expense_type = get_or_create_expense_claim_type()
		company = frappe.db.get_value("Employee", cls.employee, "company")
		cls.expense_account = frappe.db.get_value(
			"Expense Claim Account",
			{"parent": expense_type, "company": company},
			"default_account",
		)

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		set_project_budget(self.project, 10000, project_control="Strict")

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

	def _review_claim(self, claim):
		frappe.set_user(self.reviewer_email)
		review_receipts(
			claim.name,
			"verify",
			"Receipt reviewed in the accounting budget test.",
		)
		return frappe.get_doc("Expense Claim", claim.name)

	def test_expense_claim_gets_department_from_employee(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=1500)
		self.assertEqual(claim.department, self.department)

	def test_project_cost_center_is_forced_onto_expense_lines(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=500)
		claim.expenses[0].cost_center = None
		claim.save(ignore_permissions=True)
		self.assertEqual(
			claim.expenses[0].cost_center,
			frappe.db.get_value("Project", self.project, "cost_center"),
		)

	def test_submitted_claim_counts_toward_consumed_budget(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=2000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		consumed = get_consumed_amount(self.project)
		self.assertGreaterEqual(consumed, 2000)
		status = get_budget_commitment_breakdown(self.project)
		self.assertGreaterEqual(status["pending_claim_commitments"], 2000)
		self.assertEqual(status["total_committed"], consumed)
		self.assertEqual(status["available_after_commitments"], status["approved_budget"] - consumed)

	def test_budget_health_returns_one_project_row(self):
		frappe.set_user("Administrator")
		rows = get_budget_health(self.project)
		self.assertEqual(len(rows), 1)
		self.assertNotIn("department", rows[0])
		self.assertEqual(rows[0]["allocated"], 10000)
		self.assertEqual(rows[0]["project_control"], "Strict")

	def test_over_budget_claim_still_saves_with_soft_warning(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=12000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.vendor_override_reason = "Urgent reimbursement; PO not feasible."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		self.assertTrue(frappe.db.exists("Expense Claim", claim.name))
		self.assertEqual(
			frappe.db.get_value("Expense Claim", claim.name, "workflow_state"),
			"Pending Receipt Review",
		)

	def test_approve_over_budget_requires_exceedance_reason(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=12000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.vendor_override_reason = "Urgent reimbursement; PO not feasible."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		claim = self._review_claim(claim)
		self.assertEqual(claim.pending_approver, self.manager_email)

		frappe.set_user(self.manager_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		flags = get_approver_action_flags("Expense Claim", claim.name)
		self.assertFalse(flags["can_approve"])
		self.assertTrue(flags["can_escalate"])
		self.assertTrue(flags["strict_budget_blocked"])
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(claim, "Approve")

	def test_strict_over_budget_requires_authorised_override_even_with_reason(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=12000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.vendor_override_reason = "Urgent reimbursement; PO not feasible."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		claim = self._review_claim(claim)
		self.assertEqual(claim.pending_approver, self.manager_email)

		frappe.set_user(self.manager_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.budget_override_reason = "Seasonal campaign overspend is justified."
		claim.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(claim, "Approve")

	def test_authorised_strict_override_records_approval(self):
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=12000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.vendor_override_reason = "Urgent reimbursement; PO not feasible."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		claim = self._review_claim(claim)

		frappe.set_user(self.manager_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.budget_override_reason = "Board-authorised exceptional expense."
		claim.save(ignore_permissions=True)
		with patch("volunteering.volunteering.budget_service._can_override_budget", return_value=True):
			apply_workflow(claim, "Approve")
		claim.reload()
		self.assertEqual(claim.workflow_state, "Approved")

	def test_warn_only_allows_approval_without_override(self):
		frappe.set_user("Administrator")
		set_project_budget(self.project, 10000, project_control="Warn Only")
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=12000, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.vendor_override_reason = "Urgent reimbursement; PO not feasible."
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		claim = self._review_claim(claim)
		before_approval = get_budget_commitment_breakdown(self.project)

		frappe.set_user(self.manager_email)
		apply_workflow(frappe.get_doc("Expense Claim", claim.name), "Approve")
		self.assertEqual(frappe.db.get_value("Expense Claim", claim.name, "workflow_state"), "Approved")
		status = get_budget_commitment_breakdown(self.project)
		self.assertEqual(
			status["pending_claim_commitments"],
			before_approval["pending_claim_commitments"] - 12000,
		)
		self.assertEqual(status["approved_expenditure"], before_approval["approved_expenditure"] + 12000)
		self.assertEqual(status["total_committed"], before_approval["total_committed"])
		self.assertEqual(
			status["total_committed"],
			status["pending_commitments"] + status["approved_expenditure"],
		)

	def test_expense_account_budget_is_independent_of_project_ceiling(self):
		frappe.set_user("Administrator")
		set_project_budget(
			self.project,
			10000,
			project_control="No Control",
			account_control="Strict",
			account_budgets=[(self.expense_account, 400)],
		)
		before = get_account_consumed_amount(self.project, self.expense_account)
		frappe.set_user(self.employee_email)
		claim = make_expense_claim(self.employee, self.project, amount=500, owner=self.employee_email)
		claim = frappe.get_doc("Expense Claim", claim.name)
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		claim = self._review_claim(claim)

		frappe.set_user(self.manager_email)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(frappe.get_doc("Expense Claim", claim.name), "Approve")
		self.assertEqual(get_account_consumed_amount(self.project, self.expense_account), before + 500)

	def test_form_has_approval_tab_and_budget_exceedance_label(self):
		meta = frappe.get_meta("Expense Claim")
		self.assertTrue(meta.has_field("approval_routing_tab"))
		self.assertTrue(meta.has_field("budget_override_reason"))
		df = meta.get_field("budget_override_reason")
		self.assertEqual(df.label, "Budget Exceedance Reason")

		project_meta = frappe.get_meta("Project")
		self.assertFalse(bool(project_meta.get_field("fund_project_type")))
		self.assertTrue(project_meta.has_field("parent_campaign"))
		self.assertTrue(project_meta.has_field("project_budget_control"))
		self.assertTrue(project_meta.has_field("account_budget_control"))
		self.assertTrue(project_meta.has_field("account_budgets"))
		self.assertTrue(bool(project_meta.get_field("department_budgets").hidden))

	def test_employee_advance_does_not_consume_project_budget(self):
		before = get_consumed_amount(self.project)
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
		advance.flags.ignore_advance_eligibility = True
		advance.insert(ignore_permissions=True)
		apply_workflow(advance, "Submit")
		self.assertFalse(advance.project)
		self.assertEqual(get_consumed_amount(self.project), before)

	def test_expense_claim_requires_project(self):
		frappe.set_user(self.employee_email)
		with self.assertRaises(frappe.ValidationError):
			make_expense_claim(self.employee, None, amount=500)
