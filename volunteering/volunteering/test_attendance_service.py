# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from volunteering.volunteering.attendance_service import (
	is_attendance_day_in_progress,
	process_daily_attendance,
	process_employee_attendance,
)
from volunteering.volunteering.test_utils import (
	ensure_leave_allocation,
	get_or_create_allocatable_leave_type,
	get_or_create_test_employee,
	get_or_create_test_project,
)


class IntegrationTestAttendanceService(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.attendance_date = add_days(nowdate(), -2)
		self.employee = get_or_create_test_employee()
		self.project = get_or_create_test_project(self.employee)
		self._cleanup()

	def tearDown(self):
		self._cleanup()
		super().tearDown()

	def _cleanup(self):
		frappe.db.delete(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": self.attendance_date,
			},
		)
		frappe.db.delete(
			"Attendance Request",
			{
				"employee": self.employee,
				"from_date": self.attendance_date,
			},
		)
		frappe.db.delete(
			"Daily Work Log",
			{
				"employee": self.employee,
				"date": self.attendance_date,
			},
		)
		frappe.db.delete(
			"Leave Application",
			{
				"employee": self.employee,
				"from_date": self.attendance_date,
			},
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

	def _create_submitted_work_log(self, with_wfh_request=False):
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
						"time_spent_hours": 6,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def test_existing_present_attendance_is_preserved(self):
		attendance = frappe.get_doc(
			{
				"doctype": "Attendance",
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"status": "Present",
			}
		)
		attendance.insert(ignore_permissions=True)
		attendance.submit()

		process_employee_attendance(self.employee, self.attendance_date)

		self.assertEqual(self._get_attendance_status(), "Present")

	def test_submitted_work_log_marks_present(self):
		self._create_submitted_work_log()
		process_employee_attendance(self.employee, self.attendance_date)
		self.assertEqual(self._get_attendance_status(), "Present")

	def test_wfh_request_with_work_log_marks_work_from_home(self):
		self._create_submitted_work_log(with_wfh_request=True)
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

	def test_missing_log_does_not_mark_absent_for_today(self):
		today = nowdate()
		frappe.db.delete(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": today,
			},
		)

		process_employee_attendance(self.employee, today)

		self.assertTrue(is_attendance_day_in_progress(today))
		self.assertIsNone(
			frappe.db.get_value(
				"Attendance",
				{
					"employee": self.employee,
					"attendance_date": today,
					"docstatus": 1,
				},
				"status",
			)
		)

	def test_approved_leave_marks_on_leave(self):
		leave_date = nowdate()
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

		frappe.db.delete(
			"Leave Application",
			{
				"employee": self.employee,
				"from_date": leave_date,
			},
		)
		frappe.db.delete(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": leave_date,
			},
		)

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
		self.assertEqual(
			frappe.db.get_value(
				"Attendance",
				{
					"employee": self.employee,
					"attendance_date": leave_date,
					"docstatus": 1,
				},
				"status",
			),
			"On Leave",
		)

		leave.cancel()
		frappe.db.delete(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": leave_date,
			},
		)
