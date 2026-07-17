# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from volunteering.volunteering.attendance_service import (
	get_active_employees,
	is_grace_period_open,
	process_daily_attendance,
	process_employee_attendance,
)
from volunteering.volunteering.employment_type import UNPAID_EMPLOYMENT_TYPE, ensure_employment_type
from volunteering.volunteering.test_utils import (
	ensure_leave_allocation,
	get_or_create_allocatable_leave_type,
	get_or_create_test_employee,
	get_or_create_test_project,
)


class IntegrationTestAttendanceService(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.employee = get_or_create_test_employee()
		self.project = get_or_create_test_project(self.employee)
		# Allow enough backdate room for picking a non-holiday day past grace.
		if frappe.db.exists("DocType", "Daily Work Log Settings"):
			frappe.db.set_single_value("Daily Work Log Settings", "backdate_limit_days", 14)
		self.attendance_date = self._pick_working_day()
		self._cleanup()

	def _pick_working_day(self):
		"""Pick a recent weekday that is not weekly-off/holiday (grace already closed)."""
		from volunteering.volunteering.attendance_service import get_holiday_info

		candidate = add_days(nowdate(), -2)
		for _ in range(21):
			candidate = add_days(candidate, -1)
			# Skip Wednesdays (org weekly off) and weekends as common weekly offs
			if getdate(candidate).weekday() in (2, 5, 6):
				continue
			if get_holiday_info(self.employee, candidate):
				continue
			return candidate
		return add_days(nowdate(), -10)

	def tearDown(self):
		self._cleanup()
		super().tearDown()

	def _cleanup(self):
		frappe.db.delete(
			"Attendance",
			{"employee": self.employee, "attendance_date": self.attendance_date},
		)
		frappe.db.delete(
			"Attendance Request",
			{"employee": self.employee, "from_date": self.attendance_date},
		)
		frappe.db.delete(
			"Daily Work Log",
			{"employee": self.employee, "date": self.attendance_date},
		)
		frappe.db.delete(
			"Leave Application",
			{"employee": self.employee, "from_date": self.attendance_date},
		)

	def _get_attendance_status(self):
		return frappe.db.get_value(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"docstatus": 1,
			},
			"status",
		)

	def _create_wfh_request(self):
		request = frappe.get_doc(
			{
				"doctype": "Attendance Request",
				"employee": self.employee,
				"company": frappe.db.get_value("Employee", self.employee, "company"),
				"from_date": self.attendance_date,
				"to_date": self.attendance_date,
				"reason": "Work From Home",
			}
		)
		request.insert(ignore_permissions=True)
		request.submit()
		return request

	def _create_submitted_work_log(self, hours=6, with_wfh_request=False):
		if with_wfh_request:
			self._create_wfh_request()

		doc = frappe.get_doc(
			{
				"doctype": "Daily Work Log",
				"employee": self.employee,
				"date": self.attendance_date,
				"is_wfh": 1 if with_wfh_request else 0,
				"items": [
					{
						"task_title": "Attendance Test",
						"project": self.project,
						"description": "Testing attendance automation service.",
						"time_spent_hours": hours,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def test_submitted_work_log_marks_present(self):
		self._create_submitted_work_log(hours=6)
		process_employee_attendance(self.employee, self.attendance_date)
		self.assertEqual(self._get_attendance_status(), "Present")

	def test_hours_below_threshold_marks_half_day(self):
		self._create_submitted_work_log(hours=4)
		process_employee_attendance(self.employee, self.attendance_date)
		self.assertEqual(self._get_attendance_status(), "Half Day")

	def test_wfh_request_with_work_log_marks_work_from_home(self):
		self._create_submitted_work_log(hours=6, with_wfh_request=True)
		process_employee_attendance(self.employee, self.attendance_date)
		self.assertEqual(self._get_attendance_status(), "Work From Home")

	def test_wfh_request_without_work_log_marks_absent(self):
		self._create_wfh_request()
		process_employee_attendance(self.employee, self.attendance_date)
		self.assertEqual(self._get_attendance_status(), "Absent")

	def test_missing_log_marks_absent(self):
		process_employee_attendance(self.employee, self.attendance_date)
		self.assertEqual(self._get_attendance_status(), "Absent")

	def test_rerun_does_not_create_duplicate_attendance(self):
		process_employee_attendance(self.employee, self.attendance_date)
		first_count = frappe.db.count(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"docstatus": ["<", 2],
			},
		)
		process_employee_attendance(self.employee, self.attendance_date)
		second_count = frappe.db.count(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"docstatus": ["<", 2],
			},
		)
		self.assertEqual(first_count, 1)
		self.assertEqual(first_count, second_count)

	def test_manual_process_daily_attendance_marks_absent(self):
		summary = process_daily_attendance(attendance_date=self.attendance_date, manual=True)
		self.assertFalse(summary.get("skipped"))
		self.assertEqual(self._get_attendance_status(), "Absent")

	def test_grace_period_skips_absent_for_today(self):
		from unittest.mock import patch

		today = nowdate()
		frappe.db.delete("Attendance", {"employee": self.employee, "attendance_date": today})
		# Logs left behind by other suites would legitimately create attendance
		frappe.db.delete("Daily Work Log", {"employee": self.employee, "date": today})
		frappe.db.delete(
			"Attendance Request", {"employee": self.employee, "from_date": today}
		)
		# Neutralize holidays so the test is deterministic even on weekly-off days
		with patch(
			"volunteering.volunteering.attendance_service.get_holiday_info", return_value=None
		):
			action = process_employee_attendance(self.employee, today)
		self.assertTrue(is_grace_period_open(today))
		self.assertEqual(action, "skipped")
		self.assertIsNone(
			frappe.db.get_value(
				"Attendance",
				{"employee": self.employee, "attendance_date": today, "docstatus": 1},
				"status",
			)
		)

	def test_approved_leave_marks_on_leave(self):
		leave_date = self.attendance_date
		leave_type = (
			frappe.db.get_single_value("Leave Policy Settings", "default_leave_type")
			or "Privilege Leave"
		)
		get_or_create_allocatable_leave_type(leave_type)
		ensure_leave_allocation(
			self.employee,
			leave_type,
			from_date=add_days(leave_date, -30),
			to_date=add_days(leave_date, 30),
		)

		frappe.db.delete("Leave Application", {"employee": self.employee, "from_date": leave_date})
		frappe.db.delete("Attendance", {"employee": self.employee, "attendance_date": leave_date})

		leave = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": self.employee,
				"leave_type": leave_type,
				"leave_category": "Emergency",
				"from_date": leave_date,
				"to_date": leave_date,
				"status": "Approved",
			}
		)
		leave.insert(ignore_permissions=True)
		leave.submit()

		process_employee_attendance(self.employee, leave_date)
		self.assertEqual(self._get_attendance_status(), "On Leave")

		leave.cancel()

	def test_leave_takes_priority_over_hours(self):
		leave_date = self.attendance_date
		leave_type = (
			frappe.db.get_single_value("Leave Policy Settings", "default_leave_type")
			or "Privilege Leave"
		)
		get_or_create_allocatable_leave_type(leave_type)
		ensure_leave_allocation(
			self.employee,
			leave_type,
			from_date=add_days(leave_date, -30),
			to_date=add_days(leave_date, 30),
		)
		self._create_submitted_work_log(hours=8)
		# HRMS blocks leave over marked attendance; clear the auto-created record
		# so we can verify the processor prefers the approved leave over hours.
		frappe.db.delete("Attendance", {"employee": self.employee, "attendance_date": leave_date})

		leave = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": self.employee,
				"leave_type": leave_type,
				"leave_category": "Emergency",
				"from_date": leave_date,
				"to_date": leave_date,
				"status": "Approved",
			}
		)
		leave.insert(ignore_permissions=True)
		leave.submit()

		process_employee_attendance(self.employee, leave_date)
		self.assertEqual(self._get_attendance_status(), "On Leave")
		leave.cancel()

	def _find_recent_holiday(self):
		from volunteering.volunteering.attendance_service import get_holiday_info

		candidate = add_days(nowdate(), -2)
		for _ in range(14):
			candidate = add_days(candidate, -1)
			if get_holiday_info(self.employee, candidate):
				return candidate
		return None

	def test_work_on_holiday_stays_holiday_with_hours(self):
		holiday_date = self._find_recent_holiday()
		if not holiday_date:
			self.skipTest("No holiday found in backdate window")

		frappe.db.delete("Attendance", {"employee": self.employee, "attendance_date": holiday_date})
		frappe.db.delete("Daily Work Log", {"employee": self.employee, "date": holiday_date})

		doc = frappe.get_doc(
			{
				"doctype": "Daily Work Log",
				"employee": self.employee,
				"date": holiday_date,
				"items": [
					{
						"task_title": "Holiday Work",
						"project": self.project,
						"description": "Urgent campaign work on weekly off.",
						"time_spent_hours": 5,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()

		process_employee_attendance(self.employee, holiday_date)
		attendance = frappe.db.get_value(
			"Attendance",
			{"employee": self.employee, "attendance_date": holiday_date, "docstatus": 1},
			["status", "working_hours"],
			as_dict=True,
		)
		self.assertEqual(attendance.status, "Holiday")
		self.assertEqual(float(attendance.working_hours), 5.0)

		frappe.db.delete("Attendance", {"employee": self.employee, "attendance_date": holiday_date})
		frappe.db.delete("Daily Work Log", {"employee": self.employee, "date": holiday_date})

	def test_working_hours_synced_to_attendance(self):
		self._create_submitted_work_log(hours=7.5)
		process_employee_attendance(self.employee, self.attendance_date)
		working_hours = frappe.db.get_value(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"docstatus": 1,
			},
			"working_hours",
		)
		self.assertEqual(float(working_hours), 7.5)

	def test_late_log_flips_absent_to_present(self):
		# Noon job marked Absent; a late (within backdate limit) submission corrects it
		process_employee_attendance(self.employee, self.attendance_date)
		self.assertEqual(self._get_attendance_status(), "Absent")

		self._create_submitted_work_log(hours=8)
		# on_submit hook triggers refresh automatically; verify final state
		self.assertEqual(self._get_attendance_status(), "Present")

	def test_count_special_day_work(self):
		from volunteering.volunteering.attendance_service import count_special_day_work

		count = count_special_day_work(
			self.employee, add_days(nowdate(), -30), nowdate(), weekly_off_only=True
		)
		self.assertIsInstance(count, int)

	def test_unpaid_employees_excluded_from_active_list(self):
		ensure_employment_type()
		previous = frappe.db.get_value("Employee", self.employee, "employment_type")
		frappe.db.set_value("Employee", self.employee, "employment_type", UNPAID_EMPLOYMENT_TYPE)
		try:
			active = get_active_employees(self.attendance_date)
			self.assertNotIn(self.employee, active)
		finally:
			frappe.db.set_value("Employee", self.employee, "employment_type", previous)
