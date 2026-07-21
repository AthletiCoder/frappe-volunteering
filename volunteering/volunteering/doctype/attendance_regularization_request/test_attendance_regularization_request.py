# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from volunteering.volunteering.attendance_service import (
	get_holiday_info,
	process_employee_attendance,
)
from volunteering.volunteering.test_utils import (
	get_or_create_test_employee,
	get_or_create_test_project,
)

# The generic test-record generator cannot build Employee/Company chains on this
# site (fiscal year overlaps); we create our own records via test_utils instead.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Employee", "Company", "Attendance Regularization Request"]


class IntegrationTestAttendanceRegularizationRequest(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.employee = get_or_create_test_employee()
		self.project = get_or_create_test_project(self.employee)
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
			"Attendance Regularization Request",
			{"employee": self.employee, "attendance_date": self.attendance_date},
		)
		frappe.db.delete(
			"Attendance", {"employee": self.employee, "attendance_date": self.attendance_date}
		)
		frappe.db.delete(
			"Daily Work Log", {"employee": self.employee, "date": self.attendance_date}
		)

	def _make_request(self, requested_status="Present"):
		return frappe.get_doc(
			{
				"doctype": "Attendance Regularization Request",
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"requested_status": requested_status,
				"reason": "Forgot to log work; hours were actually completed.",
			}
		).insert(ignore_permissions=True)

	def test_approval_updates_attendance(self):
		# Employee was marked Absent by the noon job
		process_employee_attendance(self.employee, self.attendance_date)
		status = frappe.db.get_value(
			"Attendance",
			{"employee": self.employee, "attendance_date": self.attendance_date, "docstatus": 1},
			"status",
		)
		self.assertEqual(status, "Absent")

		request = self._make_request("Present")
		request.approve_request()

		attendance = frappe.db.get_value(
			"Attendance",
			{"employee": self.employee, "attendance_date": self.attendance_date, "docstatus": 1},
			["status", "custom_regularized"],
			as_dict=True,
		)
		self.assertEqual(attendance.status, "Present")
		self.assertEqual(int(attendance.custom_regularized or 0), 1)

	def test_noon_job_does_not_overwrite_regularized_attendance(self):
		request = self._make_request("Present")
		request.approve_request()

		# Re-running the automation must skip the regularized day
		action = process_employee_attendance(self.employee, self.attendance_date)
		self.assertEqual(action, "skipped")
		status = frappe.db.get_value(
			"Attendance",
			{"employee": self.employee, "attendance_date": self.attendance_date, "docstatus": 1},
			"status",
		)
		self.assertEqual(status, "Present")

	def test_rejection_leaves_attendance_unchanged(self):
		process_employee_attendance(self.employee, self.attendance_date)

		request = self._make_request("Present")
		request.reject_request()
		self.assertEqual(
			frappe.db.get_value(
				"Attendance Regularization Request", request.name, "status"
			),
			"Rejected",
		)
		status = frappe.db.get_value(
			"Attendance",
			{"employee": self.employee, "attendance_date": self.attendance_date, "docstatus": 1},
			"status",
		)
		self.assertEqual(status, "Absent")

	def test_duplicate_open_request_is_blocked(self):
		self._make_request("Present")
		with self.assertRaises(frappe.ValidationError):
			self._make_request("Half Day")
