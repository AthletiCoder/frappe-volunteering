"""Work log ownership, manager review, safe retries and Home access."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department, get_or_create_employee, get_or_create_user,
)
from volunteering.volunteering.work_log_portal import (
	get_tasks_app_access, get_work_log, get_work_log_workspace, review_work_log, save_work_log, work_logging_access,
	get_work_log_access, get_work_log_calendar, get_work_log_team,
)


class IntegrationTestWorkLogPortal(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		department = get_or_create_department("Work Log Portal Test")
		cls.staff = get_or_create_user("worklog.staff@example.com", ["Employee"])
		cls.manager = get_or_create_user("worklog.manager@example.com", ["Employee"])
		cls.other = get_or_create_user("worklog.other@example.com", ["Employee"])
		cls.hr = get_or_create_user("worklog.hr@example.com", ["HR User"])
		cls.unlinked = get_or_create_user("worklog.unlinked@example.com", ["App chat access"])
		cls.manager_employee = get_or_create_employee(cls.manager, department, "Work Log Manager")
		cls.employee = get_or_create_employee(cls.staff, department, "Work Log Staff")
		cls.other_employee = get_or_create_employee(cls.other, department, "Other Staff")
		frappe.db.set_value("Employee", cls.employee, "reports_to", cls.manager_employee)

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		names = frappe.get_all("Daily Work Log", filters={"employee": ["in", [self.employee, self.manager_employee, self.other_employee]]}, pluck="name")
		if names:
			frappe.db.delete("Daily Work Log Item", {"parent": ["in", names], "parenttype": "Daily Work Log"})
			frappe.db.delete("Daily Work Log", {"name": ["in", names]})
		frappe.db.delete("Attendance", {"employee": ["in", [self.employee, self.manager_employee, self.other_employee]]})
		frappe.db.set_value("Employee", self.employee, "reports_to", self.manager_employee)
		frappe.db.set_value("Employee", self.other_employee, "reports_to", None)
		frappe.set_user(self.staff)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def details(self, **updates):
		data = {
			"date": nowdate(), "notes": "Portal regression sample",
			"items": [{"task_title": "Prepare learning session", "project": "",
				"description": "Prepared exercises and checked the learning materials.", "time_spent_hours": 6, "output_link": ""}],
		}
		data.update(updates)
		return data

	def details_for(self, log, **updates):
		data = {key: log[key] for key in ("name", "modified", "date", "notes", "items")}
		data.update(updates)
		return data

	def test_guest_and_unlinked_users_cannot_access_work_logs(self):
		for user in ("Guest", self.unlinked):
			frappe.set_user(user)
			for call in (get_work_log_workspace, get_work_log):
				with self.subTest(user=user, method=call.__name__), self.assertRaises(frappe.PermissionError):
					call()

	def test_employee_can_use_app_work_logs_without_chat_role(self):
		access = get_tasks_app_access()
		self.assertFalse(access["chat_access"])
		self.assertTrue(access["work_logging"]["can_create"])
		frappe.set_user(self.unlinked)
		access = get_tasks_app_access()
		self.assertTrue(access["chat_access"])
		self.assertFalse(access["work_logging"]["can_create"])

	def test_own_draft_is_visible_and_editable_and_team_scope_is_denied(self):
		result = save_work_log(self.details())
		log = result["log"]
		self.assertTrue(log["can_edit"])
		self.assertTrue(log["is_own"])
		self.assertEqual(log["total_hours"], 6)
		self.assertEqual(len(get_work_log_workspace()["rows"]), 1)
		self.assertEqual(get_work_log(date=nowdate())["log"]["name"], log["name"])
		saved = save_work_log(self.details_for(log, notes="Updated daily summary"))
		self.assertEqual(saved["log"]["notes"], "Updated daily summary")
		self.assertNotIn("manager_remarks", saved["log"])
		with self.assertRaises(frappe.PermissionError):
			get_work_log_workspace(view="team")

	def test_submit_retries_do_not_create_extra_logs_or_attendance_updates(self):
		from volunteering.volunteering import attendance_service
		payload = self.details()
		with patch.object(attendance_service, "refresh_attendance_for_work_log", wraps=attendance_service.refresh_attendance_for_work_log) as refresh:
			submitted = save_work_log(payload, submit=1)
			retried = save_work_log(payload, submit=1)
			self.assertEqual(submitted["log"]["name"], retried["log"]["name"])
			self.assertEqual(retried["log"]["status"], "Submitted")
			self.assertFalse(retried["log"]["can_edit"])
			self.assertEqual(frappe.db.count("Daily Work Log", {"employee": self.employee, "date": nowdate()}), 1)
			refresh.assert_called_once()
		with self.assertRaises(frappe.ValidationError):
			save_work_log(self.details_for(submitted["log"], notes="Change after submission"))

	def test_manager_can_review_direct_reports_and_private_notes_stay_private(self):
		log = save_work_log(self.details(), submit=1)["log"]
		frappe.set_user(self.manager)
		workspace = get_work_log_workspace(view="team")
		self.assertIn(log["name"], [row.name for row in workspace["rows"]])
		detail = get_work_log(name=log["name"])["log"]
		self.assertTrue(detail["can_review"])
		self.assertFalse(detail["is_own"])
		self.assertFalse(detail["can_edit"])
		with self.assertRaises(frappe.PermissionError):
			save_work_log(self.details_for(detail, notes="Manager must not edit staff hours"))
		reviewed = review_work_log(log["name"], detail["modified"], "Checked with project lead.")["log"]
		self.assertEqual(reviewed["status"], "Reviewed")
		self.assertEqual(reviewed["manager_remarks"], "Checked with project lead.")
		frappe.set_user(self.staff)
		self.assertNotIn("manager_remarks", get_work_log(name=log["name"])["log"])

	def test_other_employee_cannot_access_or_review_another_log(self):
		log = save_work_log(self.details(), submit=1)["log"]
		frappe.set_user(self.other)
		self.assertEqual(get_work_log_workspace()["rows"], [])
		with self.assertRaises(frappe.PermissionError):
			get_work_log(name=log["name"])
		with self.assertRaises(frappe.PermissionError):
			review_work_log(log["name"], log["modified"])

	def test_hr_without_employee_can_review_but_cannot_create(self):
		log = save_work_log(self.details(), submit=1)["log"]
		frappe.set_user(self.hr)
		self.assertTrue(work_logging_access()["can_review_team"])
		self.assertFalse(work_logging_access()["can_create"])
		self.assertIn(log["name"], [row.name for row in get_work_log_workspace(view="team")["rows"]])
		review_work_log(log["name"], log["modified"], "HR review")
		with self.assertRaises(frappe.PermissionError):
			save_work_log(self.details())

	def test_stale_edit_cannot_overwrite_newer_changes(self):
		old = save_work_log(self.details())["log"]
		save_work_log(self.details_for(old, notes="Changed in another session"))
		with self.assertRaises(frappe.TimestampMismatchError):
			save_work_log(self.details_for(old, notes="Stale edit"))

	def test_draft_and_submission_validation(self):
		invalid = [
			self.details(date=add_days(nowdate(), 1)),
			self.details(date=add_days(nowdate(), -90)),
			self.details(items=[]),
			self.details(items=[{"task_title": "Invalid", "description": "Description is long enough", "time_spent_hours": "NaN"}]),
			self.details(items=[{"task_title": "Invalid", "description": "Description is long enough", "time_spent_hours": -1}]),
			self.details(items=[{"task_title": "Invalid", "description": "Description is long enough", "time_spent_hours": 25}]),
			self.details(items=[{"task_title": "Invalid", "description": "Too short", "time_spent_hours": 6}]),
			self.details(items=[{"task_title": "Invalid link", "description": "Description is long enough", "time_spent_hours": 6, "output_link": "javascript:alert(1)"}]),
		]
		for details in invalid:
			with self.subTest(details=details), self.assertRaises(frappe.ValidationError):
				save_work_log(details)
		self.assertFalse(frappe.db.exists("Daily Work Log", {"employee": self.employee}))

	def test_filters_and_unknown_status_are_enforced(self):
		save_work_log(self.details())
		self.assertEqual(get_work_log_workspace(status="Submitted")["rows"], [])
		self.assertEqual(len(get_work_log_workspace(status="Draft", from_date=nowdate(), to_date=nowdate())["rows"]), 1)
		with self.assertRaises(frappe.ValidationError):
			get_work_log_workspace(status="anything")
		with self.assertRaises(frappe.ValidationError):
			get_work_log_workspace(from_date=nowdate(), to_date=add_days(nowdate(), -1))

	def test_calendar_shows_hours_status_and_future_days_are_blocked(self):
		log = save_work_log(self.details())["log"]
		calendar = get_work_log_calendar()
		day = next(day for day in calendar["days"] if day["date"] == nowdate())
		self.assertEqual(day["status"], "Draft")
		self.assertEqual(day["total_hours"], 6)
		self.assertEqual(day["name"], log["name"])
		self.assertTrue(day["can_open"])
		self.assertEqual(calendar["summary"]["Draft"], 1)
		for day in calendar["days"]:
			if day["date"] > nowdate():
				self.assertEqual(day["status"], "Future")
				self.assertFalse(day["can_open"])
		with self.assertRaises(frappe.ValidationError):
			get_work_log(date=add_days(nowdate(), 1))

	def test_calendar_returns_every_day_in_month_and_not_only_first_page(self):
		from datetime import timedelta
		from calendar import monthrange
		from frappe.utils import getdate
		last = getdate(nowdate()).replace(day=1) - timedelta(days=1)
		month = last.strftime("%Y-%m")
		frappe.set_user("Administrator")
		for number in range(1, last.day + 1):
			doc = frappe.get_doc({"doctype": "Daily Work Log", "employee": self.employee,
				"date": last.replace(day=number), "items": self.details()["items"]})
			doc.flags.hr_exception_reason = "Verified previous month regression fixture"
			doc.insert(ignore_permissions=True)
		frappe.set_user(self.staff)
		calendar = get_work_log_calendar(month)
		self.assertEqual(len(calendar["days"]), monthrange(last.year, last.month)[1])
		self.assertEqual(calendar["summary"]["Draft"], last.day)
		self.assertEqual(calendar["summary"]["total_hours"], last.day * 6)

	def test_team_lists_people_even_when_they_have_no_logs(self):
		frappe.set_user(self.manager)
		people = get_work_log_team()["people"]
		self.assertIn(self.employee, [person.name for person in people])
		self.assertNotIn(self.other_employee, [person.name for person in people])
		person = next(person for person in people if person.name == self.employee)
		self.assertEqual(person.submitted, 0)
		self.assertEqual(person.total_hours, 0)
		self.assertEqual(get_work_log_team(query="no-such-person") ["people"], [])
		self.assertEqual(get_work_log_team(query="Other Staff")["people"], [])

	def test_calendar_cannot_be_used_to_read_other_employees(self):
		with self.assertRaises(frappe.PermissionError):
			get_work_log_calendar(employee=self.other_employee)
		with self.assertRaises(frappe.PermissionError):
			get_work_log_team()
		frappe.set_user(self.manager)
		self.assertFalse(get_work_log_calendar(employee=self.employee)["is_own"])
		with self.assertRaises(frappe.PermissionError):
			get_work_log_calendar(employee=self.other_employee)
		# Being higher in the hierarchy alone grants no access to an indirect report.
		frappe.set_user("Administrator")
		frappe.db.set_value("Employee", self.other_employee, "reports_to", self.employee)
		frappe.set_user(self.manager)
		with self.assertRaises(frappe.PermissionError):
			get_work_log_calendar(employee=self.other_employee)

	def test_team_calendar_cannot_create_logs_for_another_employee(self):
		frappe.set_user(self.manager)
		calendar = get_work_log_calendar(employee=self.employee)
		self.assertTrue(all(not day["can_open"] for day in calendar["days"]))
		self.assertEqual(calendar["summary"]["total_hours"], 0)

	def test_reviewed_status_updates_calendar_and_pending_review_count(self):
		log = save_work_log(self.details(), submit=1)["log"]
		frappe.set_user(self.manager)
		person = next(person for person in get_work_log_team()["people"] if person.name == self.employee)
		self.assertEqual(person.submitted, 1)
		before = get_work_log_calendar(employee=self.employee)["summary"]
		self.assertEqual(before["submitted_total"], 1)
		self.assertEqual(before["awaiting_review"], 1)
		review_work_log(log["name"], log["modified"], "Private calendar test note")
		calendar = get_work_log_calendar(employee=self.employee)
		day = next(day for day in calendar["days"] if day["date"] == nowdate())
		self.assertEqual(day["status"], "Reviewed")
		self.assertEqual(calendar["summary"]["submitted_total"], 1)
		self.assertEqual(calendar["summary"]["awaiting_review"], 0)
		self.assertEqual(calendar["summary"]["Reviewed"], 1)
		self.assertNotIn("manager_remarks", day)
		person = next(person for person in get_work_log_team()["people"] if person.name == self.employee)
		self.assertEqual(person.submitted, 0)
		self.assertEqual(person.reviewed, 1)

	def test_hr_without_employee_can_select_any_employee_calendar(self):
		frappe.set_user(self.hr)
		self.assertFalse(get_work_log_access()["can_create"])
		people = get_work_log_team(query="Other Staff")["people"]
		self.assertIn(self.other_employee, [person.name for person in people])
		self.assertEqual(get_work_log_calendar(employee=self.other_employee)["calendar_employee"].name, self.other_employee)

	def test_invalid_months_and_old_unfilled_days_are_not_editable(self):
		for month in ("2026-13", "2026-00", "2026-1", "junk", "0000-01"):
			with self.subTest(month=month), self.assertRaises(frappe.ValidationError):
				get_work_log_calendar(month)
		calendar = get_work_log_calendar()
		for day in calendar["days"]:
			if day["date"] < calendar["earliest_date"]:
				self.assertFalse(day["can_open"])

	def test_minute_durations_survive_reload_and_submission_at_hour_boundaries(self):
		for offset, total in enumerate((6, 24)):
			with self.subTest(total=total):
				items = [{"task_title": "Minute duration", "description": "Recorded precise work time in minutes.", "time_spent_hours": hours}
					for hours in ("0.016666667", str(round(total - 1 / 60, 9)))]
				draft = save_work_log(self.details(date=add_days(nowdate(), -offset), items=items))["log"]
				self.assertEqual(draft["total_hours"], total)
				loaded = get_work_log(name=draft["name"])["log"]
				submitted = save_work_log(self.details_for(loaded), submit=1)["log"]
				self.assertEqual(submitted["total_hours"], total)
				self.assertEqual(submitted["status"], "Submitted")
