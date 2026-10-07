# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.home_access import (
	classify_home_access,
	get_staff_home_page,
	guest_login_redirect_url,
	require_logged_in_or_redirect,
	set_staff_login_home,
	staff_login_target,
)
from volunteering.volunteering.home_service import (
	_accounts_actions,
	_accounts_queues,
	_compose_todos,
	_employee_draft_todos,
	_member_project_cards,
	_money_actions,
	_system_management_actions,
	_show_member_projects,
	_time_actions,
	get_home_payload,
)
from volunteering.volunteering.home_cutover import home_project_filter
from volunteering.www.volunteering import is_open_home_route


class UnitTestHomeAccess(UnitTestCase):
	def test_frappe_login_hooks_are_registered(self):
		self.assertIn(
			"volunteering.volunteering.home_access.set_staff_login_home",
			frappe.get_hooks("on_session_creation"),
		)
		self.assertIn(
			"volunteering.volunteering.home_access.get_staff_home_page",
			frappe.get_hooks("get_website_user_home_page"),
		)

	def test_login_landing_page_is_home_for_every_authenticated_user(self):
		for user in (
			"employee@example.com",
			"manager@example.com",
			"volunteer@example.com",
			"Administrator",
		):
			with self.subTest(user=user):
				self.assertEqual(staff_login_target(user), "/volunteering/home")
		self.assertIsNone(staff_login_target("Guest"))
		self.assertIsNone(staff_login_target(None))

	def test_session_creation_sets_home_for_employee_and_administrator(self):
		from types import SimpleNamespace
		from frappe.website.utils import get_home_page

		previous = frappe.local.flags.get("home_page")
		try:
			for user in ("employee@example.com", "Administrator"):
				with self.subTest(user=user):
					frappe.local.flags.pop("home_page", None)
					set_staff_login_home(SimpleNamespace(user=user))
					self.assertEqual(frappe.local.flags.home_page, "/volunteering/home")
					with patch.object(frappe, "in_test", False):
						self.assertEqual(get_home_page(), "/volunteering/home")

			frappe.local.flags.pop("home_page", None)
			set_staff_login_home(SimpleNamespace(user="Guest"))
			self.assertIsNone(frappe.local.flags.get("home_page"))
		finally:
			if previous is None:
				frappe.local.flags.pop("home_page", None)
			else:
				frappe.local.flags.home_page = previous

	def test_home_page_hook_requires_only_an_authenticated_user(self):
		self.assertEqual(get_staff_home_page("employee@example.com"), "/volunteering/home")
		self.assertEqual(get_staff_home_page("Administrator"), "/volunteering/home")
		self.assertEqual(get_staff_home_page("volunteer@example.com"), "/volunteering/home")
		self.assertIsNone(get_staff_home_page("Guest"))

	def test_everyone_can_open_home_but_other_portal_routes_keep_role_gate(self):
		self.assertTrue(is_open_home_route("/volunteering/home"))
		self.assertTrue(is_open_home_route("/volunteering/home/"))
		self.assertTrue(is_open_home_route("/volunteering/profile"))
		self.assertFalse(is_open_home_route("/volunteering/chart-of-accounts"))

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
		flags = classify_home_access(["Employee", "HR Manager"], has_employee=True, grade="Manager")
		self.assertEqual(flags["persona"], "hr")
		self.assertTrue(flags["show_people"])
		self.assertTrue(flags["show_hr_management"])
		self.assertFalse(flags["show_system_management"])
		self.assertFalse(flags["show_accounts"])

	def test_system_manager_sees_system_management_not_hr_management(self):
		flags = classify_home_access(["System Manager"], has_employee=False)
		self.assertTrue(flags["allowed"])
		self.assertTrue(flags["show_system_management"])
		self.assertFalse(flags["show_hr_management"])
		self.assertIn(
			("fiscal_years", "/volunteering/fiscal-years"),
			{(action["id"], action["route"]) for action in _system_management_actions()},
		)

	def test_coordinator_sees_programs_and_budget(self):
		flags = classify_home_access(["Employee", "NGO Coordinator"], has_employee=True, grade="Manager")
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
	def test_project_cards_only_for_non_accounts_employee_members(self):
		self.assertTrue(_show_member_projects("employee@example.com", "EMP-1", ["Employee"], False))
		self.assertFalse(_show_member_projects("manager@example.com", "EMP-2", ["Projects Manager"], True))
		self.assertFalse(_show_member_projects("accounts@example.com", "EMP-3", ["Accounts User"], False))
		self.assertFalse(_show_member_projects("accounts@example.com", "EMP-3", ["Accounts Manager"], False))
		self.assertFalse(_show_member_projects("Administrator", "EMP-4", ["Employee"], False))
		self.assertFalse(_show_member_projects("employee@example.com", None, ["Employee"], False))

	@patch("volunteering.volunteering.home_service.frappe.get_list")
	@patch("volunteering.volunteering.home_service.frappe.get_all")
	@patch("volunteering.volunteering.home_service.frappe.db.get_value", return_value="Sevamrita Foundation")
	def test_member_project_cards_only_return_basic_details_and_eligible_actions(self, _company, get_all, get_list):
		get_all.side_effect = [
			["PROJ-1", "PROJ-2"],
			[frappe._dict(name="PROJ-1", budget_status="Active"), frappe._dict(name="PROJ-2", budget_status="Closed")],
			["PROJ-1"],
		]
		get_list.return_value = [
			frappe._dict(
				name="PROJ-1", project_name="Active Project", project_purpose="Field work",
				project_type="", operational_status="Active",
				expected_start_date="2026-10-01", expected_end_date=None,
			),
			frappe._dict(
				name="PROJ-2", project_name="Active but financially closed", project_purpose="Done",
				project_type="", operational_status="Active",
				expected_start_date=None, expected_end_date=None,
			),
		]
		cards = _member_project_cards("employee@example.com", "EMP-1")
		self.assertEqual([card["name"] for card in cards], ["PROJ-1"])
		self.assertTrue(cards[0]["can_submit_expense"])
		self.assertTrue(cards[0]["can_request_advance"])
		self.assertNotIn("budget_status", cards[0])
		self.assertNotIn("total_approved_budget", cards[0])
		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["project_setup_version"], [">", 0])
		self.assertEqual(filters["is_archived"], 0)
		self.assertEqual(filters["operational_status"], "Active")
		self.assertEqual(filters["company"], "Sevamrita Foundation")

	@patch("volunteering.volunteering.home_cutover.home_project_names", return_value=[])
	def test_empty_governed_project_filter_does_not_match_blank_legacy_links(self, _names):
		self.assertEqual(
			home_project_filter("intended_project"),
			{"intended_project": ["in", ["__NO_GOVERNED_PROJECT__"]]},
		)

	@patch(
		"volunteering.volunteering.home_service.frappe.get_roles",
		return_value=["Accounts User", "Accounts Manager"],
	)
	def test_accounts_manager_home_includes_project_label_mapping(self, _roles):
		actions = _accounts_actions("accounts@example.com")
		chart = next(row for row in actions if row["id"] == "chart_of_accounts")
		self.assertEqual(chart["route"], "/volunteering/chart-of-accounts")
		opening = next(row for row in actions if row["id"] == "opening_balances")
		self.assertEqual(opening["route"], "/volunteering/opening-balances")
		donations = next(row for row in actions if row["id"] == "donations")
		self.assertEqual(donations["route"], "/volunteering/donations")
		mapping = next(row for row in actions if row["id"] == "project_account_mapping")
		self.assertEqual(mapping["route"], "/volunteering/project-account-mapping")
		returns = next(row for row in actions if row["id"] == "advance_returns")
		self.assertEqual(returns["route"], "/volunteering/advance-workflow?view=return")

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
		self.assertNotIn("vendor", [row["id"] for row in _money_actions()])
		action = next(row for row in _money_actions() if row["id"] == "invoice_generator")
		self.assertEqual(action["route"], "/volunteering/invoice-generator")
		self.assertIn("GST", action["hint"])
		combined = next(row for row in _money_actions() if row["id"] == "invoice_expense_claim")
		self.assertEqual(combined["route"], "/volunteering/invoice-expense-claim")
		self.assertIn("one flow", combined["hint"])

		claim = next(row for row in _money_actions() if row["id"] == "claim")
		self.assertEqual(claim["route"], "/volunteering/expense-claim")
		self.assertEqual(claim["list_route"], "/volunteering/expense-claims")

	@patch("volunteering.volunteering.home_service._residual_advance_count", return_value=0)
	@patch("volunteering.volunteering.home_service.frappe.get_all", return_value=[])
	@patch("volunteering.volunteering.home_service._safe_count", return_value=1)
	@patch("volunteering.volunteering.home_service.frappe.get_roles", return_value=[])
	def test_accounts_queue_hides_unfinished_vendor_payment(self, _roles, safe_count, _advances, _residual):
		self.assertNotIn("vendor_pay", [row["id"] for row in _accounts_queues()])
		self.assertNotIn("Purchase Invoice", [call.args[0] for call in safe_count.call_args_list])

	@patch("volunteering.volunteering.home_service.frappe.db.exists", return_value=True)
	@patch("volunteering.volunteering.home_service.frappe.db.has_column", return_value=True)
	@patch("volunteering.volunteering.home_service.frappe.get_all")
	@patch("volunteering.volunteering.home_service.is_home_advance", return_value=True)
	@patch("volunteering.volunteering.home_service.home_project_filter", return_value={})
	def test_draft_advance_resumes_in_home_portal(self, _filter, _home, get_all, _has_column, _exists):
		get_all.side_effect = [
			[
				frappe._dict(
					{
						"name": "HR-EAD-2026-00001",
						"creation": "2026-09-18 09:00:00",
						"modified": "2026-09-18 09:10:00",
						"advance_amount": 0,
						"workflow_state": "Draft",
					}
				)
			],
			[],
		]
		todos = _employee_draft_todos("HR-EMP-00001")
		self.assertEqual(todos[0]["route"], "/volunteering/advances/HR-EAD-2026-00001")
