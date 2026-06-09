# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from volunteering.volunteering.attendance_service import process_employee_attendance
from volunteering.volunteering.test_utils import (
	ensure_holiday_list_for_employee,
	get_or_create_allocatable_leave_type,
)


class IntegrationTestAttendanceService(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.attendance_date = add_days(nowdate(), -2)
		self.employee = self._get_or_create_employee()
		self.project = self._get_or_create_project()
		ensure_holiday_list_for_employee(self.employee, self.attendance_date)
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

	def _get_or_create_employee(self):
		employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
		if employee:
			return employee

		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			company = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": "_Test Attendance Service Company",
					"abbr": "ASC",
					"default_currency": "INR",
					"country": "India",
				}
			).insert(ignore_permissions=True).name

		return frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "Attendance Service",
				"company": company,
				"status": "Active",
				"date_of_joining": add_days(nowdate(), -60),
				"gender": "Male",
			}
		).insert(ignore_permissions=True).name

	def _get_or_create_project(self):
		project = frappe.db.get_value("Project", {}, "name")
		if project:
			return project

		company = frappe.db.get_value("Employee", self.employee, "company")
		return frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": "_Test Attendance Service Project",
				"company": company,
			}
		).insert(ignore_permissions=True).name

	def _ensure_leave_allocation(self, leave_type, leave_date=None):
		leave_date = leave_date or self.attendance_date
		existing = frappe.db.exists(
			"Leave Allocation",
			{
				"employee": self.employee,
				"leave_type": leave_type,
				"docstatus": 1,
				"from_date": ["<=", leave_date],
				"to_date": [">=", leave_date],
			},
		)
		if existing:
			return

		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": self.employee,
				"leave_type": leave_type,
				"from_date": add_days(leave_date, -30),
				"to_date": add_days(leave_date, 30),
				"new_leaves_allocated": 10,
			}
		)
		allocation.insert(ignore_permissions=True)
		allocation.submit()

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

	def test_approved_leave_marks_on_leave(self):
		leave_date = nowdate()
		ensure_holiday_list_for_employee(self.employee, leave_date)
		leave_type = frappe.db.get_value(
			"Leave Type",
			{"is_lwp": 0, "name": ["not in", ["Leave Without Pay"]]},
			"name",
		)
		if not leave_type:
			leave_type = get_or_create_allocatable_leave_type("_Test Attendance Leave")

		self._ensure_leave_allocation(leave_type, leave_date)

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

		frappe.db.delete(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": leave_date,
			},
		)

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

		frappe.db.delete("Leave Application", {"name": leave.name})
