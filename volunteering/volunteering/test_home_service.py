# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import patch

from frappe.tests import UnitTestCase

from volunteering.volunteering.home_access import (
	classify_home_access,
	guest_login_redirect_url,
	require_logged_in_or_redirect,
)
from volunteering.volunteering.home_service import (
	_compose_todos,
	_money_actions,
	_time_actions,
	get_home_payload,
)


class UnitTestHomeAccess(UnitTestCase):
	def test_employee_sees_time_and_money_not_pay_queues(self):
		flags = classify_home_access(["Employee"], has_employee=True, grade="Associate")
		self.assertTrue(flags["allowed"])
		self.assertEqual(flags["persona"], "employee")
		self.assertTrue(flags["show_time"])
		self.assertTrue(flags["show_money"])
		self.assertFalse(flags["show_accounts"])
		self.assertFalse(flags["show_budget_health"])
		self.assertFalse(flags["show_programs"])
		self.assertFalse(flags["show_people"])
		self.assertFalse(flags["show_admin"])
		self.assertFalse(flags["show_approver_inbox"])

	def test_manager_gets_approver_inbox(self):
		flags = classify_home_access(
			["Employee", "Leave Approver", "Expense Approver"],
			has_employee=True,
			grade="Manager",
		)
		self.assertEqual(flags["persona"], "manager")
		self.assertTrue(flags["show_approver_inbox"])
		self.assertTrue(flags["show_time"])
		self.assertFalse(flags["show_accounts"])
		self.assertFalse(flags["show_budget_health"])

	def test_accounts_sees_pay_queues_and_budget(self):
		flags = classify_home_access(
			["Employee", "Accounts User", "Accounts Manager"],
			has_employee=True,
			grade="Manager",
		)
		self.assertEqual(flags["persona"], "accounts")
		self.assertTrue(flags["show_accounts"])
		self.assertTrue(flags["show_budget_health"])
		self.assertTrue(flags["show_advances"])
		self.assertTrue(flags["deemphasize_self_service"])

	def test_hr_sees_people_section(self):
		flags = classify_home_access(
			["Employee", "HR Manager"], has_employee=True, grade="Manager"
		)
		self.assertEqual(flags["persona"], "hr")
		self.assertTrue(flags["show_people"])
		self.assertFalse(flags["show_accounts"])

	def test_coordinator_sees_programs_and_budget(self):
		flags = classify_home_access(
			["Employee", "NGO Coordinator"], has_employee=True, grade="Manager"
		)
		self.assertEqual(flags["persona"], "coordinator")
		self.assertTrue(flags["show_programs"])
		self.assertTrue(flags["show_budget_health"])

	def test_volunteer_without_employee_is_blocked(self):
		flags = classify_home_access(["NGO Member"], has_employee=False, grade=None)
		self.assertFalse(flags["allowed"])
		self.assertEqual(flags["persona"], "volunteer")
		self.assertFalse(flags["show_time"])
		self.assertFalse(flags["show_accounts"])

	def test_board_grade_gets_admin_and_budget(self):
		flags = classify_home_access(
			["Employee", "Accounts User"], has_employee=True, grade="Board of Directors"
		)
		self.assertTrue(flags["show_admin"])
		self.assertTrue(flags["show_budget_health"])
		self.assertIn(flags["persona"], ("admin", "accounts"))

	def test_guest_login_redirect_url_keeps_requested_path(self):
		self.assertEqual(
			guest_login_redirect_url("/volunteering/home"),
			"/login?redirect-to=%2Fvolunteering%2Fhome",
		)
		self.assertEqual(
			guest_login_redirect_url("/login"),
			"/login?redirect-to=%2Fvolunteering%2Fhome",
		)

	def test_require_logged_in_or_redirect_sends_guest_to_login(self):
		import frappe

		prev = frappe.session.user
		prev_location = frappe.flags.redirect_location
		try:
			frappe.session.user = "Guest"
			with self.assertRaises(frappe.Redirect):
				require_logged_in_or_redirect()
			location = frappe.flags.redirect_location
			self.assertTrue(location.startswith("/login?"))
			self.assertIn("redirect-to", location)
		finally:
			frappe.session.user = prev
			frappe.flags.redirect_location = prev_location

	def test_require_logged_in_or_redirect_allows_logged_in_user(self):
		import frappe

		prev = frappe.session.user
		try:
			frappe.session.user = "e2e.employee@sevamrita.local"
			require_logged_in_or_redirect()
		finally:
			frappe.session.user = prev


class UnitTestHomePayload(UnitTestCase):
	@patch("volunteering.volunteering.home_service.get_grade_for_user", return_value=None)
	@patch("volunteering.volunteering.home_service.get_employee_for_user", return_value=None)
	@patch("volunteering.volunteering.home_service.frappe.get_roles", return_value=["NGO Member"])
	def test_volunteer_payload_is_not_allowed(self, _roles, _emp, _grade):
		import frappe

		prev = frappe.session.user
		try:
			frappe.session.user = "e2e.volunteer@sevamrita.local"
			payload = get_home_payload()
		finally:
			frappe.session.user = prev
		self.assertFalse(payload["allowed"])
		self.assertEqual(payload["persona"], "volunteer")
		self.assertEqual(payload["inbox"], [])
		self.assertEqual(payload["todos"], [])
		self.assertEqual(payload["todo_count"], 0)
		self.assertFalse(payload["nav"]["budget_health"])
		self.assertFalse(payload["nav"]["advances"])
		self.assertFalse(payload["nav"]["volunteering"])

	def test_compose_todos_orders_review_pay_then_yours(self):
		todos = _compose_todos(
			[
				{
					"id": "Leave Application::L1",
					"kind": "Leave",
					"title": "Ada",
					"subtitle": "Casual",
					"route": "/desk/leave-application/L1",
					"modified": "1",
				}
			],
			[
				{
					"id": "reimburse",
					"label": "Claims to reimburse",
					"count": 2,
					"route": "/desk/expense-claim",
				},
				{"id": "empty", "label": "Skip", "count": 0, "route": "/desk/x"},
			],
			[
				{
					"id": "draft_claims",
					"label": "Draft claims",
					"count": 1,
					"route": "/desk/expense-claim",
				}
			],
		)
		self.assertEqual([row["bucket"] for row in todos], ["review", "pay", "yours"])
		self.assertEqual(todos[1]["id"], "queue::reimburse")
		self.assertEqual(todos[2]["id"], "status::draft_claims")

	def test_new_request_actions_link_to_previous_lists(self):
		leave = next(row for row in _time_actions({"leave": 2}) if row["id"] == "leave")
		self.assertEqual(leave["route"], "/desk/leave-application/new")
		self.assertEqual(leave["list_route"], "/desk/leave-application")
		self.assertEqual(leave["list_label"], "Previous leave")
		self.assertEqual(leave["pending"], 2)

	def test_money_actions_include_employee_invoice_generator(self):
		action = next(row for row in _money_actions() if row["id"] == "invoice_generator")
		self.assertEqual(action["route"], "/volunteering/invoice-generator")
		self.assertIn("GST", action["hint"])
