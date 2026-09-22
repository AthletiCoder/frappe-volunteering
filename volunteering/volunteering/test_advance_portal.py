from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from volunteering.volunteering.accounting_setup import setup_accounting_custom_fields
from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department,
	get_or_create_employee,
	get_or_create_project_with_cost_center,
	get_or_create_user,
	mute_accounting_test_emails,
	save_test_project,
	set_employee_grade,
)
from volunteering.volunteering.advance_freeze import freeze_status, set_advance_freeze
from volunteering.volunteering.advance_portal import (
	get_advance_request_form,
	save_advance_request,
)
from volunteering.volunteering.advance_workflow_portal import (
	decide_advance,
	disburse_advance,
	get_advance_work_item,
	get_advance_work_queue,
	record_advance_return,
)
from volunteering.volunteering.approval_routing import (
	escalate_document,
	get_approver_action_flags,
	get_live_workflow_transitions,
)
from volunteering.volunteering.employee_advance_controls import get_grade_advance_limit_for_employee
from volunteering.volunteering.employee_bank_accounts import (
	review_bank_account_request,
	submit_bank_account_request,
)
from volunteering.volunteering.team_portal import get_team_dashboard
from volunteering.volunteering.test_employee_bank_accounts import details as bank_request_details


class IntegrationTestAdvanceHome(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.emails = mute_accounting_test_emails()
		setup_accounting_custom_fields()
		frappe.set_user("Administrator")
		cls.manager_user = get_or_create_user(
			"advance-home-manager@example.com", ["Employee", "Expense Approver"], "Advance Manager"
		)
		cls.employee_user = get_or_create_user(
			"advance-home-employee@example.com", ["Employee"], "Advance Employee"
		)
		cls.other_user = get_or_create_user("advance-home-other@example.com", ["Employee"], "Other Employee")
		cls.accounts_user = get_or_create_user(
			"advance-home-accounts@example.com", ["Employee", "Accounts User"], "Advance Accounts"
		)
		cls.accounts_manager_user = get_or_create_user(
			"advance-home-accounts-manager@example.com", ["Employee", "Accounts Manager"], "Advance Accounts Manager"
		)
		cls.department = get_or_create_department("Advance Home Tests")
		cls.manager = get_or_create_employee(cls.manager_user, cls.department, "Advance Manager")
		cls.employee = get_or_create_employee(cls.employee_user, cls.department, "Advance Employee")
		cls.other = get_or_create_employee(cls.other_user, cls.department, "Other Employee")
		set_employee_grade(cls.manager, "Manager")
		set_employee_grade(cls.employee, "Associate", reports_to=cls.manager)
		set_employee_grade(cls.other, "Associate")
		cls.approval_chain = [(cls.manager_user, cls.manager, "Manager")]
		for index, grade in enumerate(
			("Vice President", "President", "Director", "CEO", "Executive Board", "Board of Directors")
		):
			user = get_or_create_user(
				f"advance-home-authority-{index}@example.com", ["Employee", "Expense Approver"], grade
			)
			employee = get_or_create_employee(user, cls.department, grade)
			set_employee_grade(employee, grade)
			frappe.db.set_value("Employee", cls.approval_chain[-1][1], "reports_to", employee)
			cls.approval_chain.append((user, employee, grade))
		frappe.db.set_value("Employee", cls.approval_chain[-1][1], "reports_to", None)
		cls.project = get_or_create_project_with_cost_center()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		cls.emails.close()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.delete("Employee Advance Freeze Event", {"employee": self.employee})
		frappe.db.delete("Employee Advance", {"employee": self.employee})
		project = frappe.get_doc("Project", self.project)
		project.project_setup_version = 1
		project.project_purpose = project.project_purpose or "Advance portal project"
		project.project_owner = self.manager_user
		project.operational_status = "Active"
		project.budget_status = "Active"
		project.is_archived = 0
		if self.employee_user not in [row.user for row in project.project_participants]:
			project.append("project_participants", {"user": self.employee_user, "access_level": "Basic"})
		save_test_project(project)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Employee Advance Freeze Event", {"employee": self.employee})
		frappe.db.delete("Employee Advance", {"employee": self.employee})
		super().tearDown()

	def payload(self):
		return {
			"intended_project": self.project,
			"amount": 500,
			"purpose": "Local project materials",
			"required_by_date": add_days(nowdate(), 2),
			"expected_settlement_date": add_days(nowdate(), 14),
			"advance_use": "My expenses",
			"additional_note": "Home portal test",
			"support_filename": "",
			"support_content": "",
		}

	def bank(self):
		return {
			"bank_name": "Approved Bank",
			"account_number_masked": "••••1234",
			"ifsc": "TEST0123456",
		}

	@patch("volunteering.volunteering.advance_portal.get_approved_bank_details")
	def test_defaults_expose_only_eligible_project_and_masked_bank(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		data = get_advance_request_form()
		self.assertIn(self.project, [row["value"] for row in data["projects"]])
		self.assertEqual(data["approved_bank"]["account_number_masked"], "••••1234")
		self.assertNotIn("account_number", data["approved_bank"])
		self.assertEqual(data["approver"]["user"], self.manager_user)
		self.assertIsNone(data["limit"]["limit"])

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_employee_can_save_eligible_draft(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		result = save_advance_request(self.payload(), 0)
		doc = frappe.get_doc("Employee Advance", result["name"])
		self.assertEqual(doc.employee, self.employee)
		self.assertEqual(doc.intended_project, self.project)
		self.assertEqual(doc.advance_use, "My expenses")
		self.assertFalse(doc.project)
		self.assertEqual(doc.docstatus, 0)

	def test_manager_freeze_is_audited_and_blocks_new_requests(self):
		frappe.set_user(self.manager_user)
		status = set_advance_freeze(self.employee, 1, "Previous advance needs reconciliation")
		self.assertTrue(status["frozen"])
		self.assertEqual(freeze_status(self.employee)["acted_by"], self.manager_user)

		frappe.set_user(self.employee_user)
		with patch(
			"volunteering.volunteering.employee_bank_accounts.get_approved_bank_details",
			return_value=self.bank(),
		):
			with self.assertRaises(frappe.ValidationError):
				save_advance_request(self.payload(), 0)

	def test_non_manager_cannot_freeze_and_team_is_direct_only(self):
		frappe.set_user(self.other_user)
		with self.assertRaises(frappe.PermissionError):
			set_advance_freeze(self.employee, 1, "Not my report")

		frappe.set_user(self.manager_user)
		team = get_team_dashboard()["team"]
		self.assertIn(self.employee, [row["employee"] for row in team])
		self.assertNotIn(self.other, [row["employee"] for row in team])

	def test_team_advance_requires_a_direct_report(self):
		frappe.set_user(self.employee_user)
		payload = self.payload()
		payload["advance_use"] = "Team expenses"
		with patch(
			"volunteering.volunteering.employee_bank_accounts.get_approved_bank_details",
			return_value=self.bank(),
		):
			with self.assertRaises(frappe.ValidationError):
				save_advance_request(payload, 0)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_submission_enters_existing_approval_routing(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		result = save_advance_request(self.payload(), 1)
		doc = frappe.get_doc("Employee Advance", result["name"])
		self.assertTrue(result["submitted"])
		self.assertEqual(doc.workflow_state, "Pending Approval")
		self.assertEqual(doc.pending_approver, self.manager_user)
		self.assertEqual(doc.paid_amount, 0)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_home_queue_and_decision_are_scoped_to_current_reviewer(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		name = save_advance_request(self.payload(), 1)["name"]
		self.assertEqual(get_advance_work_queue()["counts"]["approval"], 0)
		with self.assertRaises(frappe.PermissionError):
			get_advance_work_item(name)
		with self.assertRaises(frappe.PermissionError):
			decide_advance(name, "approve")
		with self.assertRaises(frappe.PermissionError):
			disburse_advance(name, {"amount": 500, "paid_from": "Cash - SF"})

		frappe.set_user(self.other_user)
		with self.assertRaises(frappe.PermissionError):
			get_advance_work_item(name)

		frappe.set_user(self.manager_user)
		queue = get_advance_work_queue()
		self.assertIn(name, [row["name"] for row in queue["queues"]["approval"]])
		item = get_advance_work_item(name)
		self.assertTrue(item["approval_flags"]["can_approve"])
		self.assertEqual(item["approval_flags"]["approval_exposure"], 500)
		self.assertNotIn("advance_account", item)
		decide_advance(name, "approve", "Approved for project materials")
		self.assertEqual(frappe.db.get_value("Employee Advance", name, "workflow_state"), "Approved")
		self.assertEqual(frappe.db.get_value("Employee Advance", name, "paid_amount"), 0)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_home_reviewer_uses_live_outstanding_and_cannot_skip_chain(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		first = save_advance_request({**self.payload(), "amount": 1000}, 1)["name"]
		save_advance_request({**self.payload(), "amount": 1500}, 1)
		frappe.set_user(self.manager_user)
		item = get_advance_work_item(first)
		self.assertEqual(item["approval_flags"]["approval_exposure"], 2500)
		self.assertFalse(item["approval_flags"]["can_approve"])
		with self.assertRaisesRegex(frappe.ValidationError, "must be escalated"):
			decide_advance(first, "approve")
		decide_advance(first, "escalate", "Total outstanding exceeds my authority")
		self.assertEqual(
			frappe.db.get_value("Employee Advance", first, "pending_approver"),
			self.approval_chain[1][0],
		)
		with self.assertRaises(frappe.PermissionError):
			decide_advance(first, "reject", "Too late")

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_accounts_home_cash_disbursement_creates_real_payment_entry(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		name = save_advance_request(self.payload(), 1)["name"]
		frappe.set_user(self.manager_user)
		decide_advance(name, "approve")
		frappe.set_user(self.accounts_user)
		queue = get_advance_work_queue()
		self.assertIn(name, [row["name"] for row in queue["queues"]["disbursement"]])
		item = get_advance_work_item(name)
		cash = next((row for row in item["payment"]["accounts"] if row["type"] == "Cash"), None)
		self.assertIsNotNone(cash)
		with self.assertRaises(frappe.ValidationError):
			disburse_advance(name, {"amount": 501, "paid_from": cash["value"]})
		result = disburse_advance(
			name,
			{"amount": 500, "paid_from": cash["value"], "posting_date": nowdate()},
		)
		payment = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual(payment.docstatus, 1)
		self.assertEqual(payment.paid_from, cash["value"])
		self.assertEqual(payment.party, self.employee)
		self.assertEqual(payment.references[0].reference_doctype, "Employee Advance")
		self.assertEqual(payment.references[0].reference_name, name)
		self.assertEqual(frappe.db.get_value("Employee Advance", name, "paid_amount"), 500)
		with self.assertRaises(frappe.ValidationError):
			disburse_advance(name, {"amount": 500, "paid_from": cash["value"]})

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_accounts_home_records_partial_and_final_unused_advance_return(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		name = save_advance_request(self.payload(), 1)["name"]
		with self.assertRaises(frappe.PermissionError):
			record_advance_return(name, {"amount": 100, "received_into": "Cash - SF"})
		frappe.set_user(self.manager_user)
		decide_advance(name, "approve")
		frappe.set_user(self.accounts_user)
		with self.assertRaises(frappe.ValidationError):
			record_advance_return(name, {"amount": 100, "received_into": "Cash - SF"})
		item = get_advance_work_item(name)
		cash = next(row for row in item["payment"]["accounts"] if row["type"] == "Cash")
		disburse_advance(name, {"amount": 500, "paid_from": cash["value"]})
		self.assertIn(name, [row["name"] for row in get_advance_work_queue()["queues"]["return"]])
		item = get_advance_work_item(name)
		self.assertTrue(item["access"]["return"])
		self.assertEqual(item["return_options"]["maximum"], 500)
		with patch(
			"volunteering.volunteering.advance_workflow_portal._pending_claim_names",
			return_value=["HR-EXP-PENDING"],
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Resolve claims"):
				record_advance_return(name, {"amount": 100, "received_into": cash["value"]})
		with self.assertRaises(frappe.ValidationError):
			record_advance_return(name, {"amount": 501, "received_into": cash["value"]})
		result = record_advance_return(name, {"amount": 300, "received_into": cash["value"]})
		entry = frappe.get_doc("Journal Entry", result["journal_entry"])
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.accounts[0].reference_name, name)
		self.assertEqual(entry.accounts[1].account, cash["value"])
		self.assertEqual(result["returned_amount"], 300)
		self.assertEqual(result["residual_amount"], 200)
		result = record_advance_return(name, {"amount": 200, "received_into": cash["value"]})
		self.assertEqual(result["returned_amount"], 500)
		self.assertEqual(result["residual_amount"], 0)
		self.assertNotIn(name, [row["name"] for row in get_advance_work_queue()["queues"]["return"]])

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_accounts_home_bank_return_requires_receipt_reference(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		name = save_advance_request(self.payload(), 1)["name"]
		frappe.set_user(self.manager_user)
		decide_advance(name, "approve")
		frappe.set_user(self.accounts_user)
		item = get_advance_work_item(name)
		cash = next(row for row in item["payment"]["accounts"] if row["type"] == "Cash")
		disburse_advance(name, {"amount": 500, "paid_from": cash["value"]})
		bank_account = next(row for row in get_advance_work_item(name)["return_options"]["accounts"] if row["type"] == "Bank")
		with self.assertRaisesRegex(frappe.ValidationError, "reference number"):
			record_advance_return(name, {"amount": 100, "received_into": bank_account["value"]})
		result = record_advance_return(
			name,
			{
				"amount": 100,
				"received_into": bank_account["value"],
				"reference_no": "LOCAL-RETURN-TEST-001",
				"reference_date": nowdate(),
			},
		)
		entry = frappe.get_doc("Journal Entry", result["journal_entry"])
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.voucher_type, "Bank Entry")
		self.assertEqual(entry.cheque_no, "LOCAL-RETURN-TEST-001")
		self.assertEqual(entry.accounts[1].account, bank_account["value"])
		self.assertEqual(result["residual_amount"], 400)

	def test_accounts_home_bank_disbursement_requires_approved_destination(self):
		frappe.set_user(self.employee_user)
		request = submit_bank_account_request(bank_request_details())
		frappe.set_user(self.accounts_manager_user)
		approved = review_bank_account_request(request["name"], "approve", request["modified"])
		frappe.set_user(self.employee_user)
		name = save_advance_request(self.payload(), 1)["name"]
		frappe.set_user(self.manager_user)
		decide_advance(name, "approve")
		frappe.set_user(self.accounts_user)
		item = get_advance_work_item(name)
		bank = next((row for row in item["payment"]["accounts"] if row["type"] == "Bank"), None)
		self.assertIsNotNone(bank)
		self.assertTrue(item["payment"]["approved_bank"]["account_number_masked"].endswith("9012"))
		self.assertNotIn("123456789012", str(item["payment"]["approved_bank"]))
		with self.assertRaises(frappe.ValidationError):
			disburse_advance(name, {"amount": 500, "paid_from": bank["value"]})
		result = disburse_advance(
			name,
			{
				"amount": 500,
				"paid_from": bank["value"],
				"reference_no": "LOCAL-ADVANCE-TEST-001",
				"reference_date": nowdate(),
			},
		)
		payment = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual(payment.docstatus, 1)
		self.assertEqual(payment.party_bank_account, approved["bank_account"])
		self.assertEqual(payment.reference_no, "LOCAL-ADVANCE-TEST-001")
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Payment Entry",
					"reference_name": payment.name,
					"owner": self.accounts_user,
				},
			)
		)

	def test_approved_bank_is_required_server_side(self):
		frappe.set_user(self.employee_user)
		with patch(
			"volunteering.volunteering.employee_bank_accounts.get_approved_bank_details",
			return_value=None,
		):
			with self.assertRaises(frappe.ValidationError):
				save_advance_request(self.payload())

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_multiple_home_requests_can_be_pending_at_once(self, bank):
		bank.return_value = self.bank()
		# Old database values must not silently re-enable the removed restriction.
		frappe.db.set_single_value("Volunteering Accounting Settings", "max_unsettled_advances", 1)
		frappe.clear_document_cache("Volunteering Accounting Settings", "Volunteering Accounting Settings")
		frappe.set_user(self.employee_user)
		names = []
		for amount in (1500, 2000, 1000):
			result = save_advance_request({**self.payload(), "amount": amount}, 1)
			names.append(result["name"])
			doc = frappe.get_doc("Employee Advance", result["name"])
			self.assertEqual(doc.workflow_state, "Pending Approval")
			self.assertEqual(doc.pending_approver, self.manager_user)
		self.assertEqual(len(set(names)), 3)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_approval_authority_rechecks_live_total_outstanding(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		first = save_advance_request({**self.payload(), "amount": 1000}, 1)

		frappe.set_user(self.manager_user)
		initial = get_approver_action_flags("Employee Advance", first["name"])
		self.assertTrue(initial["can_approve"])
		self.assertEqual(initial["approval_exposure"], 1000)
		self.assertIn(
			"Approve",
			[
				row.action
				for row in get_live_workflow_transitions(frappe.get_doc("Employee Advance", first["name"]))
			],
		)

		# A second request arrives after the manager has already opened the first.
		# The server must re-read exposure when the manager acts.
		frappe.set_user(self.employee_user)
		second = save_advance_request({**self.payload(), "amount": 1500}, 1)
		frappe.set_user(self.manager_user)
		live = get_approver_action_flags("Employee Advance", first["name"])
		self.assertEqual(live["request_amount"], 1000)
		self.assertEqual(live["other_outstanding"], 1500)
		self.assertEqual(live["approval_exposure"], 2500)
		self.assertFalse(live["can_approve"])
		self.assertTrue(live["can_escalate"])
		self.assertNotIn(
			"Approve",
			[
				row.action
				for row in get_live_workflow_transitions(frappe.get_doc("Employee Advance", first["name"]))
			],
		)
		with self.assertRaisesRegex(frappe.ValidationError, "approval limit is below"):
			apply_workflow(frappe.get_doc("Employee Advance", first["name"]), "Approve")

		# Rejecting the other request immediately lowers the live exposure. The
		# first request can then be approved without changing its stored route.
		apply_workflow(frappe.get_doc("Employee Advance", second["name"]), "Reject")
		refreshed = get_approver_action_flags("Employee Advance", first["name"])
		self.assertEqual(refreshed["approval_exposure"], 1000)
		self.assertTrue(refreshed["can_approve"])
		self.assertIn(
			"Approve",
			[
				row.action
				for row in get_live_workflow_transitions(frappe.get_doc("Employee Advance", first["name"]))
			],
		)
		apply_workflow(frappe.get_doc("Employee Advance", first["name"]), "Approve")

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_full_paid_residual_does_not_block_additional_requests(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		first = save_advance_request({**self.payload(), "amount": 2000}, 1)
		frappe.set_user(self.manager_user)
		apply_workflow(frappe.get_doc("Employee Advance", first["name"]), "Approve")
		# Disbursement fixture: the entire paid advance remains unclaimed/unreturned.
		frappe.db.set_value("Employee Advance", first["name"], {"paid_amount": 2000, "status": "Paid"})
		frappe.set_user(self.employee_user)
		for _ in range(2):
			result = save_advance_request({**self.payload(), "amount": 2000}, 1)
			self.assertEqual(result["workflow_state"], "Pending Approval")
		first_doc = frappe.get_doc("Employee Advance", first["name"])
		self.assertEqual(first_doc.paid_amount, 2000)
		self.assertEqual(first_doc.claimed_amount, 0)
		self.assertEqual(first_doc.return_amount, 0)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_multiple_desk_requests_can_be_submitted(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		for _ in range(3):
			doc = frappe.get_doc(
				{
					"doctype": "Employee Advance",
					"employee": self.employee,
					"company": frappe.db.get_value("Employee", self.employee, "company"),
					"posting_date": nowdate(),
					"advance_amount": 150000,
					"purpose": "Multiple Desk request regression",
					"intended_project": self.project,
					"required_by_date": add_days(nowdate(), 2),
					"expected_settlement_date": add_days(nowdate(), 14),
					"advance_use": "My expenses",
				}
			).insert()
			apply_workflow(doc, "Submit")
			doc.reload()
			self.assertEqual(doc.workflow_state, "Pending Approval")
			self.assertEqual(doc.pending_approver, self.manager_user)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_request_above_former_grade_limit_is_allowed_with_open_requests(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		save_advance_request({**self.payload(), "amount": 2000}, 1)
		result = save_advance_request({**self.payload(), "amount": 150000}, 1)
		doc = frappe.get_doc("Employee Advance", result["name"])
		self.assertEqual(doc.advance_amount, 150000)
		self.assertEqual(doc.pending_approver, self.manager_user)
		self.assertIsNone(get_grade_advance_limit_for_employee(self.employee)["limit"])

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_amount_authority_boundaries_visit_every_approver_in_order(self, bank):
		bank.return_value = self.bank()
		cases = (
			(2000, 0),
			(2000.01, 1),
			(5000, 1),
			(5000.01, 2),
			(10000, 2),
			(10000.01, 3),
			(25000, 3),
			(25000.01, 4),
			(50000, 4),
			(50000.01, 5),
			(100000, 5),
			(100000.01, 6),
			(999999999.01, 6),
		)
		for amount, final_index in cases:
			with self.subTest(amount=amount):
				frappe.set_user(self.employee_user)
				result = save_advance_request({**self.payload(), "amount": amount}, 1)
				for index, (user, _employee, grade) in enumerate(self.approval_chain[: final_index + 1]):
					frappe.set_user(user)
					doc = frappe.get_doc("Employee Advance", result["name"])
					self.assertEqual(doc.pending_approver, user)
					self.assertTrue(frappe.has_permission("Employee Advance", "read", doc))
					flags = get_approver_action_flags("Employee Advance", doc.name)
					self.assertEqual(flags["can_approve"], index == final_index)
					if index < final_index:
						with self.assertRaises(frappe.ValidationError):
							apply_workflow(doc, "Approve")
						escalate_document(
							"Employee Advance", doc.name, f"Reviewed by {grade}; above my authority"
						)
					else:
						with self.assertRaises(frappe.ValidationError):
							escalate_document("Employee Advance", doc.name, "Unnecessary escalation")
						apply_workflow(frappe.get_doc("Employee Advance", doc.name), "Approve")
						self.assertEqual(
							frappe.db.get_value("Employee Advance", doc.name, "workflow_state"), "Approved"
						)
				# Keep each boundary subtest independent. Directly mark the approved
				# fixture settled so it no longer contributes to live outstanding
				# exposure for the next amount in this same test method.
				frappe.set_user("Administrator")
				frappe.db.set_value(
					"Employee Advance",
					result["name"],
					{"status": "Claimed", "claimed_amount": amount},
					update_modified=False,
				)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_higher_approver_access_is_limited_to_assigned_pending_request(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		first = save_advance_request({**self.payload(), "amount": 7000}, 1)
		second = save_advance_request({**self.payload(), "amount": 8000}, 1)
		frappe.set_user(self.manager_user)
		escalate_document("Employee Advance", first["name"], "Reviewed; needs higher authority")
		vice_user = self.approval_chain[1][0]
		frappe.set_user(vice_user)
		first_doc = frappe.get_doc("Employee Advance", first["name"])
		second_doc = frappe.get_doc("Employee Advance", second["name"])
		self.assertTrue(frappe.has_permission("Employee Advance", "write", first_doc))
		self.assertFalse(frappe.has_permission("Employee Advance", "read", second_doc))
		visible = frappe.get_list("Employee Advance", pluck="name")
		self.assertIn(first["name"], visible)
		self.assertNotIn(second["name"], visible)
		first_doc.advance_amount = 6000
		with self.assertRaises(frappe.ValidationError):
			first_doc.save()
		escalate_document("Employee Advance", first["name"], "Reviewed; needs President approval")
		self.assertFalse(
			frappe.has_permission(
				"Employee Advance", "read", frappe.get_doc("Employee Advance", first["name"])
			)
		)
		# An unrelated employee cannot gain access by supplying their own assignment.
		frappe.set_user(self.other_user)
		second_doc.pending_approver = self.other_user
		self.assertFalse(frappe.has_permission("Employee Advance", "read", second_doc))

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_assigned_higher_approver_can_reject(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		result = save_advance_request({**self.payload(), "amount": 10000}, 1)
		frappe.set_user(self.manager_user)
		escalate_document("Employee Advance", result["name"], "Reviewed; needs higher authority")
		frappe.set_user(self.approval_chain[1][0])
		apply_workflow(frappe.get_doc("Employee Advance", result["name"]), "Reject")
		self.assertEqual(
			frappe.db.get_value("Employee Advance", result["name"], "workflow_state"), "Rejected"
		)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_board_cannot_bypass_assigned_chain_or_approve_own_advance(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		result = save_advance_request({**self.payload(), "amount": 150000}, 1)
		board_user, board_employee, _grade = self.approval_chain[-1]
		frappe.set_user(board_user)
		for action in ("Approve", "Reject"):
			with self.assertRaises(frappe.ValidationError):
				apply_workflow(frappe.get_doc("Employee Advance", result["name"]), action)
		frappe.set_user("Administrator")
		project = frappe.get_doc("Project", self.project)
		project.append("project_participants", {"user": board_user, "access_level": "Basic"})
		save_test_project(project)
		frappe.set_user(board_user)
		own = save_advance_request({**self.payload(), "amount": 150000}, 1)
		self.assertEqual(frappe.db.get_value("Employee Advance", own["name"], "employee"), board_employee)
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(frappe.get_doc("Employee Advance", own["name"]), "Approve")

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_reviewer_cannot_forge_assignment_to_skip_chain(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		result = save_advance_request({**self.payload(), "amount": 150000}, 1)
		frappe.set_user(self.manager_user)
		doc = frappe.get_doc("Employee Advance", result["name"])
		doc.pending_approver = self.approval_chain[-1][0]
		doc.escalation_reason = "Attempt to skip intermediate reviewers"
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		doc.reload()
		self.assertEqual(doc.pending_approver, self.manager_user)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_reviewer_cannot_reduce_amount_on_direct_submit_to_bypass_authority(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		result = save_advance_request({**self.payload(), "amount": 150000}, 1)
		frappe.set_user(self.manager_user)
		doc = frappe.get_doc("Employee Advance", result["name"])
		doc.advance_amount = 500
		doc.workflow_state = "Approved"
		with self.assertRaisesRegex(frappe.ValidationError, "request details cannot be changed"):
			doc.submit()
		doc.reload()
		self.assertEqual(doc.advance_amount, 150000)
		self.assertEqual(doc.workflow_state, "Pending Approval")
		self.assertEqual(doc.docstatus, 0)

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_ineligible_project_and_dates_are_rejected(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.other_user)
		with self.assertRaises(frappe.PermissionError):
			save_advance_request(self.payload())
		frappe.set_user(self.employee_user)
		for overrides in (
			{"intended_project": ""},
			{"required_by_date": add_days(nowdate(), -1)},
			{"expected_settlement_date": nowdate()},
			{"amount": -100},
			{"amount": "nan"},
			{"employee": self.other},
		):
			with self.subTest(overrides=overrides), self.assertRaises(frappe.ValidationError):
				save_advance_request({**self.payload(), **overrides})

	@patch("volunteering.volunteering.employee_bank_accounts.get_approved_bank_details")
	def test_frozen_existing_draft_cannot_be_submitted_from_desk(self, bank):
		bank.return_value = self.bank()
		frappe.set_user(self.employee_user)
		result = save_advance_request(self.payload())
		frappe.set_user(self.manager_user)
		set_advance_freeze(self.employee, 1, "Review outstanding documentation")
		frappe.set_user(self.employee_user)
		doc = frappe.get_doc("Employee Advance", result["name"])
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(doc, "Submit")
		doc.reload()
		self.assertEqual(doc.workflow_state, "Draft")

	def test_unfreeze_retains_immutable_history(self):
		frappe.set_user(self.manager_user)
		with self.assertRaises(frappe.ValidationError):
			set_advance_freeze(self.employee, 1, "")
		set_advance_freeze(self.employee, 1, "Resolve documentation")
		status = set_advance_freeze(self.employee, 0, "Documentation resolved")
		self.assertFalse(status["frozen"])
		self.assertEqual(frappe.db.count("Employee Advance Freeze Event", {"employee": self.employee}), 2)
		event = frappe.get_doc(
			"Employee Advance Freeze Event",
			frappe.db.get_value(
				"Employee Advance Freeze Event", {"employee": self.employee, "action": "Freeze"}
			),
		)
		frappe.set_user("Administrator")
		event.reason = "Altered history"
		with self.assertRaises(frappe.PermissionError):
			event.save()
		with self.assertRaises(frappe.PermissionError):
			event.delete()
