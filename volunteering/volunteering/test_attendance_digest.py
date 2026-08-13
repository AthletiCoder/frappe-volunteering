# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from volunteering.volunteering.accounting_test_utils import (
	get_or_create_employee,
	get_or_create_user,
	set_employee_grade,
)
from volunteering.volunteering.api.attendance_digest import (
	_build_rows,
	_digest_recipients,
	_is_due,
	_render_html,
	_row_for_employee,
	send_work_log_digest,
)
from volunteering.volunteering.attendance_service import get_holiday_info
from volunteering.volunteering.leave_setup import WEEKLY_OFF_DAY
from volunteering.volunteering.test_utils import (
	get_or_create_test_employee,
	get_or_create_test_project,
)


class IntegrationTestAttendanceDigest(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.employee = get_or_create_test_employee()
		self.project = get_or_create_test_project(self.employee)
		# Allow enough backdate room for picking a non-holiday day past grace.
		frappe.db.set_single_value("Daily Work Log Settings", "backdate_limit_days", 14)
		self.attendance_date = self._pick_working_day()
		self._cleanup()

	def tearDown(self):
		self._cleanup()
		super().tearDown()

	def _pick_working_day(self):
		candidate = add_days(nowdate(), -2)
		for _ in range(21):
			candidate = add_days(candidate, -1)
			if getdate(candidate).weekday() in (2, 5, 6):
				continue
			if get_holiday_info(self.employee, candidate):
				continue
			return candidate
		return add_days(nowdate(), -10)

	def _cleanup(self):
		frappe.db.delete(
			"Daily Work Log", {"employee": self.employee, "date": self.attendance_date}
		)
		frappe.db.delete(
			"Attendance", {"employee": self.employee, "attendance_date": self.attendance_date}
		)

	def _emp_dict(self):
		return frappe._dict(
			frappe.db.get_value(
				"Employee",
				self.employee,
				["name", "employee_name", "department", "relieving_date"],
				as_dict=True,
			)
		)

	def test_missing_log_is_flagged(self):
		row = _row_for_employee(self._emp_dict(), self.attendance_date)
		self.assertTrue(row["missing_log"])
		self.assertEqual(row["hours"], 0)

	def test_low_hours_is_flagged(self):
		doc = frappe.get_doc(
			{
				"doctype": "Daily Work Log",
				"employee": self.employee,
				"date": self.attendance_date,
				"items": [
					{
						"task_title": "Partial Day",
						"project": self.project,
						"description": "Half day of campaign coordination.",
						"time_spent_hours": 3,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()

		row = _row_for_employee(self._emp_dict(), self.attendance_date)
		self.assertFalse(row["missing_log"])
		self.assertTrue(row["low_hours"])
		self.assertEqual(row["hours"], 3)
		self.assertIn(self.project, row["project_breakdown"])
		self.assertIn("Partial Day", row["task_summary"])

	def test_full_day_is_not_flagged(self):
		doc = frappe.get_doc(
			{
				"doctype": "Daily Work Log",
				"employee": self.employee,
				"date": self.attendance_date,
				"notes": "Completed all planned campaign tasks.",
				"items": [
					{
						"task_title": "Full Day",
						"project": self.project,
						"description": "Full day of campaign coordination.",
						"time_spent_hours": 7,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()

		row = _row_for_employee(self._emp_dict(), self.attendance_date)
		self.assertFalse(row["missing_log"])
		self.assertFalse(row["low_hours"])
		self.assertIn("Completed all planned", row["comments"])

	def test_html_renders_all_rows(self):
		rows = _build_rows(self.attendance_date)
		html = _render_html(self.attendance_date, rows)
		self.assertIn("<table", html)
		for row in rows:
			self.assertIn(frappe.utils.escape_html(row["employee_name"]), html)

	def test_recipients_include_extra_addresses(self):
		settings = frappe._dict({"board_digest_extra_recipients": "extra@example.org"})
		recipients = _digest_recipients(settings)
		self.assertIn("extra@example.org", recipients)

	def test_recipients_from_board_grades(self):
		board_email = get_or_create_user("digest-board@example.com", ["Employee"], "Digest Board")
		board_employee = get_or_create_employee(board_email, None, "Digest Board Employee")
		set_employee_grade(board_employee, "Executive Board")

		settings = frappe._dict({"digest_recipient_roles": ""})
		self.assertIn(board_email, _digest_recipients(settings))

	def test_daily_digest_skips_wednesday_weekly_off(self):
		# Find a Wednesday and a non-Wednesday relative to today.
		day = getdate(nowdate())
		wednesday = add_days(day, (WEEKLY_OFF_DAY - day.weekday()) % 7)
		thursday = add_days(wednesday, 1)
		self.assertEqual(wednesday.weekday(), WEEKLY_OFF_DAY)
		self.assertFalse(_is_due("Daily", wednesday))
		self.assertTrue(_is_due("Daily", thursday))

		result = send_work_log_digest(reference_date=wednesday, force=False)
		self.assertTrue(result.get("skipped"))
		self.assertEqual(result.get("reason"), "weekly off")
