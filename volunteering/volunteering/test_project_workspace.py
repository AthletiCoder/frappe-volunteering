import base64
import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department,
	get_or_create_employee,
	get_or_create_expense_account,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	mute_accounting_test_emails,
)
from volunteering.volunteering.home_access import classify_home_access
from volunteering.volunteering.home_service import _project_actions
from volunteering.volunteering.project_proposals import (
	backfill_unassigned_project_proposals,
	get_proposals,
	remove_unused_project,
	review_proposal,
	save_proposal,
	submit_proposal,
	upload_proposal_document,
)
from volunteering.volunteering.project_workspace import (
	get_project,
	get_projects,
	get_setup_options,
	validate_project_claim_access,
)


class UnitTestProjectHome(UnitTestCase):
	def test_all_project_roles_can_open_home(self):
		for role in ("Project Proposer", "Projects User", "Projects Manager", "Project Viewer"):
			self.assertTrue(classify_home_access([role], False)["allowed"])

	def test_home_actions_distinguish_proposal_and_manager_queue(self):
		self.assertEqual(_project_actions({"show_projects": False}), [])
		self.assertEqual(_project_actions({"show_projects": True})[0]["id"], "approved_projects")
		actions = _project_actions(
			{"show_projects": True, "can_create_projects": True, "can_review_projects": True}
		)
		self.assertEqual(
			{row["id"] for row in actions},
			{
				"approved_projects",
				"create_project",
				"my_project_requests",
				"review_project_proposals",
			},
		)


class IntegrationTestProjectGovernance(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.email_patch = mute_accounting_test_emails()
		frappe.set_user("Administrator")
		base = frappe.get_doc("Project", get_or_create_project_with_cost_center())
		cls.company, cls.cost_center = base.company, base.cost_center
		cls.account = get_or_create_expense_account(cls.company)
		cls.proposer = get_or_create_user("project-proposer@example.com", ["Employee", "Project Proposer"])
		cls.manager = get_or_create_user("project-manager@example.com", ["Employee", "Projects Manager"])
		cls.other_manager = get_or_create_user(
			"project-manager-2@example.com", ["Employee", "Projects Manager"]
		)
		cls.accounts_manager = get_or_create_user(
			"project-accounts-manager@example.com", ["Employee", "Accounts Manager"]
		)
		cls.basic = get_or_create_user("project-basic@example.com", ["Employee"])
		cls.financial = get_or_create_user("project-financial@example.com", ["Employee"])
		cls.viewer = get_or_create_user("project-viewer@example.com", ["Employee", "Project Viewer"])
		cls.outsider = get_or_create_user("project-outsider@example.com", ["Employee", "Project Proposer"])
		department = get_or_create_department("Project Governance Test")
		with patch("volunteering.volunteering.leave_setup.assign_leave_policy_to_employee"):
			for user in (
				cls.proposer,
				cls.manager,
				cls.other_manager,
				cls.accounts_manager,
				cls.basic,
				cls.financial,
				cls.viewer,
				cls.outsider,
			):
				get_or_create_employee(user, department)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		cls.email_patch.close()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user(self.proposer)
		self.data = {
			"project_name": "Governed " + frappe.generate_hash(length=8),
			"project_purpose": "Deliver a tested community activity",
			"project_owner": self.proposer,
			"participants": [
				{"user": self.proposer, "access_level": "Basic"},
				{"user": self.basic, "access_level": "Basic"},
				{"user": self.financial, "access_level": "Financial"},
			],
			"operational_status": "Active",
			"cost_center": self.cost_center,
			"total_approved_budget": 10000,
			"project_budget_control": "Strict",
			"account_budget_control": "Warn Only",
			"account_budgets": [
				{
					"employee_label": "Materials",
					"approved_amount": 8000,
					"is_active": 1,
				}
			],
		}
		self.request = save_proposal(self.data, reason="Initial proposal", assigned_approver=self.manager)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def submit(self):
		frappe.set_user(self.proposer)
		self.request = submit_proposal(self.request["name"], self.request["modified"])
		return self.request

	def approve(self, manager=None, data=None):
		self.submit()
		frappe.set_user(manager or self.manager)
		self.request = review_proposal(
			self.request["name"], "approve", self.request["modified"], comments="Reviewed", data=data
		)
		return self.request

	def test_new_proposal_waits_for_assigned_manager_but_all_managers_can_view(self):
		self.assertFalse(self.request["project"])
		self.assertFalse(frappe.db.exists("Project", {"project_name": self.data["project_name"]}))
		self.submit()
		self.assertFalse(frappe.db.exists("Project", {"project_name": self.data["project_name"]}))
		frappe.set_user(self.other_manager)
		self.assertEqual(self.request["name"], get_proposals()[0].name)
		with self.assertRaises(frappe.PermissionError):
			review_proposal(
				self.request["name"],
				"approve",
				self.request["modified"],
				comments="Not assigned",
			)
		frappe.set_user(self.manager)
		approved = review_proposal(
			self.request["name"], "approve", self.request["modified"], comments="Assigned approval"
		)
		self.assertEqual(approved["proposal_status"], "Approved")
		self.assertTrue(frappe.db.exists("Project", approved["project"]))

	def test_legacy_pending_proposal_is_returned_for_manager_assignment(self):
		self.submit()
		frappe.db.set_value(
			"Project Proposal", self.request["name"], "assigned_approver", None, update_modified=False
		)
		frappe.set_user("Administrator")
		backfill_unassigned_project_proposals()
		doc = frappe.get_doc("Project Proposal", self.request["name"])
		self.assertEqual(doc.proposal_status, "Correction Required")
		self.assertEqual(doc.events[-1].action, "Returned for manager assignment")

	def test_manager_can_edit_approve_return_and_proposer_resubmit(self):
		self.submit()
		frappe.set_user(self.manager)
		edited = {**self.data, "project_name": self.data["project_name"] + " manager edited"}
		approved = review_proposal(
			self.request["name"], "approve", self.request["modified"], comments="Edited", data=edited
		)
		self.assertEqual(
			frappe.db.get_value("Project", approved["project"], "project_name"), edited["project_name"]
		)
		self.assertIn("Manager edited request", [row["action"] for row in approved["events"]])
		frappe.set_user(self.proposer)
		returned = save_proposal(
			{**self.data, "project_name": self.data["project_name"] + " returned"},
			assigned_approver=self.manager,
		)
		returned = submit_proposal(returned["name"], returned["modified"])
		frappe.set_user(self.manager)
		returned = review_proposal(returned["name"], "return", returned["modified"], comments="Clarify scope")
		frappe.set_user(self.proposer)
		resaved = save_proposal(
			{**self.data, "project_name": self.data["project_name"] + " corrected"},
			proposal=returned["name"],
			modified=returned["modified"],
			reason="Clarified",
		)
		self.assertEqual(
			submit_proposal(resaved["name"], resaved["modified"])["proposal_status"], "Pending Approval"
		)

	def test_manager_can_reject_and_nonmanager_cannot_decide(self):
		self.submit()
		frappe.set_user(self.proposer)
		with self.assertRaises(frappe.PermissionError):
			review_proposal(
				self.request["name"],
				"approve",
				self.request["modified"],
				comments="Self approval is forbidden",
			)
		frappe.set_user(self.manager)
		rejected = review_proposal(
			self.request["name"],
			"reject",
			self.request["modified"],
			comments="Outside the current programme scope",
		)
		self.assertEqual(rejected["proposal_status"], "Rejected")
		self.assertFalse(frappe.db.exists("Project", {"project_name": self.data["project_name"]}))
		self.assertEqual(rejected["events"][-1]["action"], "Rejected")

	def test_later_details_budgets_and_members_wait_for_approval(self):
		approved = self.approve()
		project = frappe.get_doc("Project", approved["project"])
		frappe.set_user(self.manager)
		change = save_proposal(
			{
				"project_purpose": "New scope",
				"participants": [{"user": self.proposer, "access_level": "Financial"}],
				"total_approved_budget": 15000,
			},
			project=project.name,
			reason="Expand work",
			assigned_approver=self.manager,
		)
		change = submit_proposal(change["name"], change["modified"])
		project.reload()
		self.assertNotEqual(project.project_purpose, "New scope")
		self.assertEqual(project.total_approved_budget, 10000)
		self.assertEqual(len(project.project_participants), 3)
		frappe.set_user(self.manager)
		review_proposal(change["name"], "approve", change["modified"], comments="Approved expansion")
		project.reload()
		self.assertEqual(project.project_purpose, "New scope")
		self.assertEqual(project.total_approved_budget, 15000)
		self.assertEqual(
			[(row.user, row.access_level) for row in project.project_participants],
			[(self.proposer, "Basic")],
		)

	def test_pending_is_locked_and_stale_approval_is_blocked(self):
		approved = self.approve()
		frappe.set_user(self.proposer)
		change = save_proposal(
			{"project_purpose": "Pending"},
			project=approved["project"],
			reason="Reason",
			assigned_approver=self.manager,
		)
		change = submit_proposal(change["name"], change["modified"])
		with self.assertRaises(frappe.PermissionError):
			save_proposal(
				{"project_purpose": "Tampered"}, proposal=change["name"], modified=change["modified"]
			)
		frappe.db.set_value(
			"Project", approved["project"], "project_name", "Concurrent metadata", update_modified=True
		)
		frappe.set_user(self.manager)
		with self.assertRaises(frappe.TimestampMismatchError):
			review_proposal(change["name"], "approve", change["modified"], comments="Stale")

	def test_proposer_viewer_and_manager_scopes(self):
		approved = self.approve()
		frappe.set_user(self.outsider)
		self.assertNotIn(approved["project"], [row.name for row in get_projects()["projects"]])
		self.assertFalse(get_proposals())
		frappe.set_user(self.viewer)
		self.assertIn(approved["project"], [row.name for row in get_projects()["projects"]])
		with self.assertRaises(frappe.PermissionError):
			save_proposal({"project_purpose": "Viewer edit"}, project=approved["project"], reason="No")
		frappe.set_user(self.manager)
		self.assertIn(approved["project"], [row.name for row in get_projects()["projects"]])

	def test_all_members_can_claim_but_only_owner_and_financial_roles_see_amounts(self):
		approved = self.approve()
		for user in (self.basic, self.financial):
			frappe.set_user(user)
			validate_project_claim_access(
				frappe.get_doc({"doctype": "Purchase Order", "owner": user, "project": approved["project"]})
			)
		frappe.set_user(self.basic)
		basic = get_project(approved["project"])
		self.assertNotIn("total_approved_budget", basic)
		self.assertNotIn("account_budgets", basic)
		self.assertEqual(basic["permitted_accounts"][0]["employee_label"], "Materials")
		frappe.set_user(self.financial)
		former_financial_member = get_project(approved["project"])
		self.assertNotIn("total_approved_budget", former_financial_member)
		frappe.set_user(self.proposer)
		owner = get_project(approved["project"])
		self.assertEqual(owner["total_approved_budget"], 10000)
		self.assertEqual(sum(row["approved_amount"] for row in owner["account_budgets"]), 10000)
		self.assertEqual(owner["financial_status"]["approved_budget"], 10000)
		self.assertEqual(owner["financial_status"]["total_committed"], owner["committed"])
		frappe.set_user(self.accounts_manager)
		accounts = get_project(approved["project"])
		self.assertEqual(accounts["total_approved_budget"], 10000)

	def test_expense_breakup_adds_others_and_cannot_exceed_total(self):
		approved = self.approve()
		project = frappe.get_doc("Project", approved["project"])
		self.assertEqual(
			[(row.employee_label, row.approved_amount) for row in project.account_budgets],
			[("Materials", 8000), ("Others", 2000)],
		)
		frappe.set_user(self.proposer)
		labels = get_setup_options(project.name)["expense_breakup_labels"]
		self.assertIn("Materials", labels)
		self.assertNotIn("Others", labels)
		request = save_proposal(
			{
				"total_approved_budget": 1000,
				"account_budgets": [{"employee_label": "Materials", "approved_amount": 1001, "is_active": 1}],
			},
			project=project.name,
			reason="Invalid reduction",
			assigned_approver=self.manager,
		)
		with self.assertRaisesRegex(frappe.ValidationError, "exceeds the total project budget"):
			submit_proposal(request["name"], request["modified"])
		self.assertFalse(frappe.has_permission("Payment Entry", "create"))

	def test_approved_supporting_documents_respect_membership_visibility(self):
		basic_content = base64.b64encode(b"basic project plan").decode()
		financial_content = base64.b64encode(b"confidential approved budget").decode()
		frappe.set_user(self.proposer)
		self.request = upload_proposal_document(
			self.request["name"],
			"plan.txt",
			basic_content,
			self.request["modified"],
			"Basic",
		)
		self.request = upload_proposal_document(
			self.request["name"],
			"budget.txt",
			financial_content,
			self.request["modified"],
			"Financial",
		)
		approved = self.approve()

		frappe.set_user(self.basic)
		basic = get_project(approved["project"])
		self.assertEqual(len(basic["attachments"]), 1)
		self.assertTrue(basic["attachments"][0]["file_name"].startswith("plan"))

		frappe.set_user(self.financial)
		former_financial_member = get_project(approved["project"])
		self.assertEqual(len(former_financial_member["attachments"]), 1)

		frappe.set_user(self.proposer)
		financial = get_project(approved["project"])
		self.assertEqual(len(financial["attachments"]), 2)
		self.assertEqual(
			{row["file_name"].split(".")[0].rstrip("0123456789abcdef") for row in financial["attachments"]},
			{"plan", "budget"},
		)
		budget_file = next(row for row in financial["attachments"] if row["file_name"].startswith("budget"))
		frappe.set_user(self.basic)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("File", budget_file["name"]).get_content()

	def test_nonmember_claim_and_direct_project_edit_are_blocked(self):
		approved = self.approve()
		frappe.set_user(self.outsider)
		with self.assertRaises(frappe.PermissionError):
			validate_project_claim_access(
				frappe.get_doc(
					{"doctype": "Purchase Order", "owner": self.outsider, "project": approved["project"]}
				)
			)
		frappe.set_user(self.manager)
		project = frappe.get_doc("Project", approved["project"])
		project.project_purpose = "Direct bypass"
		with self.assertRaisesRegex(frappe.PermissionError, "proposal"):
			project.save(ignore_permissions=True)

	def test_proposal_history_is_immutable(self):
		frappe.set_user(self.manager)
		doc = frappe.get_doc("Project Proposal", self.request["name"])
		doc.title = "Rewritten"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "retained"):
			doc.delete(ignore_permissions=True)

	def test_proposal_values_and_events_are_preserved(self):
		approved = self.approve()
		doc = frappe.get_doc("Project Proposal", approved["name"])
		self.assertEqual(json.loads(doc.proposal_data)["total_approved_budget"], 10000)
		self.assertEqual([row.action for row in doc.events][-2:], ["Submitted for approval", "Approved"])

	def test_manager_removes_unused_project_recoverably_with_history(self):
		approved = self.approve()
		frappe.set_user(self.manager)
		project = frappe.get_doc("Project", approved["project"])
		removed = remove_unused_project(project.name, str(project.modified), "Duplicate test project")
		project.reload()
		self.assertEqual(removed["proposal_status"], "Approved")
		self.assertEqual(project.operational_status, "Cancelled")
		self.assertEqual(project.is_archived, 1)
		self.assertTrue(frappe.db.exists("Project Proposal", removed["name"]))

	def test_project_with_financial_records_cannot_be_removed(self):
		approved = self.approve()
		frappe.set_user(self.manager)
		project = frappe.get_doc("Project", approved["project"])
		with patch("volunteering.volunteering.project_workspace.has_financial_records", return_value=True):
			with self.assertRaisesRegex(frappe.ValidationError, "financial records"):
				remove_unused_project(project.name, str(project.modified), "Project already has spending")
		project.reload()
		self.assertFalse(project.is_archived)
