# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.attendance_request_permissions import has_permission

MANAGER_EMAIL = "volunteering_test_manager@example.com"
REPORT_EMAIL = "volunteering_test_report@example.com"


class IntegrationTestAttendanceRequestPermissions(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.manager = self._ensure_employee("Test Manager", MANAGER_EMAIL)
		self.report = self._ensure_employee("Test Report", REPORT_EMAIL)
		frappe.db.set_value("Employee", self.report, "reports_to", self.manager)

	def _ensure_employee(self, first_name, email):
		employee = frappe.db.get_value("Employee", {"user_id": email}, "name")
		if employee:
			return employee

		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first_name,
					"send_welcome_email": 0,
					"roles": [{"role": "Employee"}],
				}
			).insert(ignore_permissions=True)

		company = frappe.db.get_value("Company", {}, "name")
		return frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": first_name,
				"company": company,
				"status": "Active",
				"date_of_joining": "2020-01-01",
				"date_of_birth": "1990-01-01",
				"gender": "Male",
				"user_id": email,
			}
		).insert(ignore_permissions=True).name

	def _make_request_doc(self):
		return frappe._dict(
			{
				"doctype": "Attendance Request",
				"employee": self.report,
			}
		)

	def test_manager_can_submit_reports_request(self):
		doc = self._make_request_doc()
		self.assertTrue(has_permission(doc, "submit", MANAGER_EMAIL))
		self.assertTrue(has_permission(doc, "read", MANAGER_EMAIL))
		self.assertFalse(has_permission(doc, "write", MANAGER_EMAIL))

	def test_employee_cannot_submit_own_request(self):
		doc = self._make_request_doc()
		self.assertFalse(has_permission(doc, "submit", REPORT_EMAIL))
		self.assertTrue(has_permission(doc, "read", REPORT_EMAIL))
		self.assertTrue(has_permission(doc, "write", REPORT_EMAIL))

	def test_unrelated_employee_has_no_access(self):
		doc = self._make_request_doc()
		self.assertFalse(has_permission(doc, "read", "someone_else@example.com"))

	def test_custom_docperm_grants_employee_submit(self):
		submit = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "Attendance Request", "role": "Employee", "permlevel": 0},
			"submit",
		)
		self.assertEqual(int(submit or 0), 1)
