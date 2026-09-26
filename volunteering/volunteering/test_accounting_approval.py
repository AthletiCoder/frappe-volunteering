# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import base64

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.accounting_setup import (
	ensure_accounting_roles,
	ensure_receipt_reviewer_permissions,
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
from volunteering.volunteering.expense_account_classification import (
	CLASSIFICATION_COMPLETE,
	PENDING_ACCOUNTS_CLASSIFICATION,
)
from volunteering.volunteering.expense_claim_workflow_portal import (
	classify_expense_claim_accounts,
	decide_expense_claim,
	get_expense_claim_work_item,
	get_expense_claim_work_queue,
)
from volunteering.volunteering.receipt_review import (
	PENDING_RECEIPT_REVIEW,
	RECEIPT_CORRECTION_REQUIRED,
	REVIEW_STATUS_PENDING,
	REVIEW_STATUS_VERIFIED,
	review_receipts,
)


class IntegrationTestAccountingApproval(IntegrationTestCase):
	"""End-to-end grade + reports_to approval flow for Expense Claims.

	Chain: employee (Associate, approve 0) -> manager (Manager, approve 2000)
	-> director (Director, approve 25000), where the band is Employee.grade.
	The workflow routes Draft -> receipt review -> Pending Approval, gated by
	the independent reviewer and then `pending_approver`.
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
		ensure_accounting_roles()
		ensure_receipt_reviewer_permissions()
		reload_accounting_workflows()
		ensure_workflow_actions()

		cls.project = get_or_create_project_with_cost_center()
		cls.employee_email = get_or_create_user("employee-acct@example.com", ["Employee"], "Employee User")
		cls.manager_email = get_or_create_user("manager-acct@example.com", ["Employee"], "Manager User")
		cls.director_email = get_or_create_user("director-acct@example.com", ["Employee"], "Director User")
		cls.reviewer_email = get_or_create_user(
			"receipt-reviewer-acct@example.com",
			["Expense Receipt Reviewer"],
			"Receipt Reviewer",
		)
		cls.accounts_email = get_or_create_user(
			"accounts-manager-acct@example.com",
			["Accounts Manager"],
			"Accounts Manager",
		)
		# Authority comes from the grade below, not from a board role.
		cls.board_chair_email = get_or_create_user(
			"board-chair-acct@example.com",
			["Employee"],
			"Board Chair",
		)
		cls.department = get_or_create_department("Operations", cls.manager_email)
		cls.employee = get_or_create_employee(cls.employee_email, cls.department)
		cls.manager_employee = get_or_create_employee(cls.manager_email, cls.department, "Manager Employee")
		cls.director_employee = get_or_create_employee(
			cls.director_email, cls.department, "Director Employee"
		)
		cls.board_chair_employee = get_or_create_employee(
			cls.board_chair_email, cls.department, "Board Chair Employee"
		)
		cls.reviewer_employee = get_or_create_employee(
			cls.reviewer_email, cls.department, "Receipt Reviewer Employee"
		)
		cls.accounts_employee = get_or_create_employee(
			cls.accounts_email, cls.department, "Accounts Manager Employee"
		)

		set_employee_grade(cls.employee, "Associate", reports_to=cls.manager_employee)
		set_employee_grade(cls.manager_employee, "Manager", reports_to=cls.director_employee)
		set_employee_grade(
			cls.director_employee,
			"Director",
			reports_to=cls.board_chair_employee,
		)
		set_employee_grade(cls.board_chair_employee, "Board of Directors")
		set_employee_grade(cls.reviewer_employee, "Associate", reports_to=cls.director_employee)
		set_employee_grade(cls.accounts_employee, "Associate", reports_to=cls.director_employee)
		cls.expense_accounts = frappe.get_all(
			"Account",
			filters={
				"company": frappe.db.get_value("Project", cls.project, "company"),
				"root_type": "Expense",
				"is_group": 0,
				"disabled": 0,
			},
			pluck="name",
			order_by="name asc",
			limit=2,
		)
		if len(cls.expense_accounts) < 2:
			frappe.throw("Accounting approval tests require two leaf Expense accounts.")

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
					[
						self.employee,
						self.manager_employee,
						self.director_employee,
						self.reviewer_employee,
					],
				]
			},
		)
		super().tearDown()

	def _review_claim(self, claim):
		frappe.set_user(self.reviewer_email)
		review_receipts(
			claim.name,
			"verify",
			"Receipt reviewed in the approval test.",
		)
		return frappe.get_doc("Expense Claim", claim.name)

	def _submit_claim_as(self, user, amount=1500, employee=None, vendor_reason=None, review=True):
		employee = employee or self.employee
		frappe.set_user(user)
		claim = make_expense_claim(employee, self.project, amount=amount, owner=user)
		claim = frappe.get_doc("Expense Claim", claim.name)
		if vendor_reason:
			claim.vendor_override_reason = vendor_reason
		claim.save(ignore_permissions=True)
		apply_workflow(claim, "Submit")
		claim = frappe.get_doc("Expense Claim", claim.name)
		return self._review_claim(claim) if review else claim

	def _classify_claim(self, claim, allocations=None):
		frappe.set_user(self.accounts_email)
		claim.reload()
		allocations = allocations or [
			{
				"expense_detail": row.name,
				"allocations": [
					{"expense_account": self.expense_accounts[0], "amount": row.sanctioned_amount}
				],
			}
			for row in claim.expenses
		]
		classify_expense_claim_accounts(claim.name, allocations, "Final Accounts classification.")
		claim.reload()
		return claim

	def test_low_value_claim_routes_to_manager(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500, review=False)
		self.assertEqual(claim.workflow_state, PENDING_RECEIPT_REVIEW)
		self.assertFalse(claim.pending_approver)
		self.assertFalse(claim.expense_approver)

		frappe.set_user(self.manager_email)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(frappe.get_doc("Expense Claim", claim.name), "Approve")

		claim = self._review_claim(claim)
		self.assertEqual(claim.workflow_state, PENDING_APPROVAL)
		self.assertEqual(claim.pending_approver, self.manager_email)

	def test_manager_can_approve_low_value_claim(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		frappe.set_user(self.manager_email)
		approved = frappe.get_doc("Expense Claim", claim.name)
		apply_workflow(approved, "Approve")
		approved.reload()
		self.assertEqual(approved.workflow_state, PENDING_ACCOUNTS_CLASSIFICATION)
		self.assertEqual(approved.docstatus, 0)
		approved = self._classify_claim(approved)
		self.assertEqual(approved.workflow_state, "Approved")
		self.assertEqual(approved.docstatus, 1)
		self.assertEqual(approved.account_classification_status, CLASSIFICATION_COMPLETE)

	def test_home_queue_and_partial_sanction_use_the_real_workflow(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500, review=False)
		frappe.set_user(self.reviewer_email)
		queue = get_expense_claim_work_queue()
		self.assertIn(claim.name, [row["name"] for row in queue["queues"]["receipt_review"]])

		claim = self._review_claim(claim)
		frappe.set_user(self.manager_email)
		queue = get_expense_claim_work_queue()
		self.assertIn(claim.name, [row["name"] for row in queue["queues"]["approval"]])
		item = get_expense_claim_work_item(claim.name)
		self.assertTrue(item["access"]["approval"])
		self.assertTrue(item["approval_flags"]["can_approve"])
		decide_expense_claim(
			claim.name,
			"approve",
			{item["expenses"][0]["name"]: 1200},
			"Partial sanction from Home.",
		)
		claim.reload()
		self.assertEqual(claim.workflow_state, PENDING_ACCOUNTS_CLASSIFICATION)
		self.assertEqual(claim.docstatus, 0)
		self.assertEqual(claim.total_sanctioned_amount, 1200)

		frappe.set_user(self.accounts_email)
		queue = get_expense_claim_work_queue()
		self.assertIn(claim.name, [row["name"] for row in queue["queues"]["classification"]])
		item = get_expense_claim_work_item(claim.name)
		self.assertTrue(item["access"]["classification"])
		self.assertFalse(item["access"]["reimbursement"])
		self.assertGreaterEqual(len(item["classification"]["accounts"]), 2)
		claim = self._classify_claim(
			claim,
			[
				{
					"expense_detail": claim.expenses[0].name,
					"allocations": [
						{"expense_account": self.expense_accounts[0], "amount": 700},
						{"expense_account": self.expense_accounts[1], "amount": 500},
					],
				}
			],
		)
		self.assertEqual(claim.workflow_state, "Approved")
		self.assertEqual(claim.docstatus, 1)
		gl_amounts = {
			row.account: row.debit
			for row in frappe.get_all(
				"GL Entry",
				filters={"voucher_type": "Expense Claim", "voucher_no": claim.name, "debit": [">", 0]},
				fields=["account", "debit"],
			)
		}
		self.assertEqual(gl_amounts[self.expense_accounts[0]], 700)
		self.assertEqual(gl_amounts[self.expense_accounts[1]], 500)

	def test_home_work_item_rejects_unrelated_employee(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500, review=False)
		frappe.set_user(self.director_email)
		with self.assertRaises(frappe.PermissionError):
			get_expense_claim_work_item(claim.name)

	def test_reviewer_cannot_edit_claim_and_can_verify_with_notes_only(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500, review=False)
		frappe.set_user(self.reviewer_email)
		self.assertFalse(frappe.get_doc("Expense Claim", claim.name).has_permission("write"))
		review_receipts(claim.name, "verify", "Receipt reviewed; no checklist is required.")
		claim.reload()
		self.assertEqual(claim.receipt_review_status, REVIEW_STATUS_VERIFIED)
		self.assertEqual(claim.workflow_state, PENDING_APPROVAL)
		self.assertFalse(claim.receipt_review_checklist)

	def test_reviewer_role_has_no_accounts_or_payment_access(self):
		self.assertFalse(frappe.has_permission("Account", "read", user=self.reviewer_email))
		self.assertFalse(frappe.has_permission("Payment Entry", "create", user=self.reviewer_email))

	def test_receipt_correction_and_resubmission_clear_prior_review(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500, review=False)
		frappe.set_user(self.reviewer_email)
		review_receipts(claim.name, "request_correction", "Upload a legible full receipt.")
		claim.reload()
		self.assertEqual(claim.workflow_state, RECEIPT_CORRECTION_REQUIRED)
		self.assertEqual(claim.receipt_review_status, "Correction Required")
		self.assertEqual(claim.receipt_reviewed_by, self.reviewer_email)

		frappe.set_user(self.employee_email)
		apply_workflow(claim, "Re-submit")
		claim.reload()
		self.assertEqual(claim.workflow_state, PENDING_RECEIPT_REVIEW)
		self.assertEqual(claim.receipt_review_status, REVIEW_STATUS_PENDING)
		self.assertFalse(claim.receipt_reviewed_by)
		self.assertFalse(claim.reviewed_attachments)

	def test_attachment_change_resets_verified_review(self):
		claim = self._submit_claim_as(self.employee_email, amount=1500)
		self.assertEqual(claim.receipt_review_status, REVIEW_STATUS_VERIFIED)
		self.assertTrue(claim.reviewed_attachments)

		frappe.set_user("Administrator")
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"replacement-{claim.name}.png",
				"attached_to_doctype": "Expense Claim",
				"attached_to_name": claim.name,
				"content": base64.b64decode(
					"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
					"ASsJTYQAAAAASUVORK5CYII="
				),
				"is_private": 1,
			}
		).insert(ignore_permissions=True)
		claim.reload()
		self.assertEqual(claim.workflow_state, PENDING_RECEIPT_REVIEW)
		self.assertEqual(claim.receipt_review_status, REVIEW_STATUS_PENDING)
		self.assertFalse(claim.pending_approver)
		self.assertFalse(claim.reviewed_attachments)

	def test_reviewer_cannot_verify_own_claim(self):
		claim = self._submit_claim_as(
			self.reviewer_email,
			amount=500,
			employee=self.reviewer_employee,
			review=False,
		)
		frappe.set_user(self.reviewer_email)
		with self.assertRaises(frappe.ValidationError):
			review_receipts(
				claim.name,
				"verify",
				"Self review attempt.",
			)

	def test_mid_value_claim_visits_manager_then_escalates_to_director(self):
		# The manager must review first even though the claim exceeds their limit.
		claim = self._submit_claim_as(self.employee_email, amount=5000)
		self.assertEqual(claim.workflow_state, PENDING_APPROVAL)
		self.assertEqual(claim.pending_approver, self.manager_email)

		frappe.set_user(self.manager_email)
		item = get_expense_claim_work_item(claim.name)
		self.assertFalse(item["approval_flags"]["can_approve"])
		self.assertTrue(item["approval_flags"]["can_escalate"])
		escalate_document("Expense Claim", claim.name, "Claim exceeds the Manager limit")
		claim.reload()
		self.assertEqual(claim.pending_approver, self.director_email)

		frappe.set_user(self.director_email)
		item = get_expense_claim_work_item(claim.name)
		self.assertTrue(item["approval_flags"]["can_approve"])

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
		claim = self._submit_claim_as(self.manager_email, amount=500, employee=self.manager_employee)
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

		frappe.set_user(self.director_email)
		escalate_document("Expense Claim", claim.name, "Amount above the Director limit")
		claim.reload()
		self.assertEqual(claim.pending_approver, self.board_chair_email)

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
		self.assertEqual(resubmit.workflow_state, PENDING_RECEIPT_REVIEW)
		resubmit = self._review_claim(resubmit)
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
