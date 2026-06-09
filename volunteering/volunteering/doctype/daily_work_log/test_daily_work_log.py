# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

IGNORE_TEST_RECORD_DEPENDENCIES = ["Employee", "Company", "Project"]


class IntegrationTestDailyWorkLog(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.employee = self._get_or_create_employee()
		self.project = self._get_or_create_project()

	def _get_or_create_employee(self):
		employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
		if employee:
			return employee

		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			company = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": "_Test Daily Work Log Company",
					"abbr": "DWLC",
					"default_currency": "INR",
					"country": "India",
				}
			).insert(ignore_permissions=True).name

		return frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "Daily Work Log",
				"company": company,
				"status": "Active",
				"date_of_joining": add_days(nowdate(), -30),
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
				"project_name": "_Test Daily Work Log Project",
				"company": company,
			}
		).insert(ignore_permissions=True).name

	def _make_work_log(self, **kwargs):
		date = kwargs.pop("date", nowdate())
		doc = frappe.get_doc(
			{
				"doctype": "Daily Work Log",
				"employee": self.employee,
				"date": date,
				"items": [
					{
						"task_title": "Test Task",
						"project": self.project,
						"description": "Worked on attendance automation tests.",
						"time_spent_hours": 5,
					}
				],
				**kwargs,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def test_permission_hooks_are_importable(self):
		from volunteering import hooks

		self.assertTrue(
			callable(frappe.get_attr(hooks.permission_query_conditions["Daily Work Log"]))
		)
		self.assertTrue(callable(frappe.get_attr(hooks.has_permission["Daily Work Log"])))

	def test_total_hours_is_calculated(self):
		doc = self._make_work_log()
		self.assertEqual(doc.total_hours, 5)

	def test_duplicate_employee_date_is_rejected(self):
		date = add_days(nowdate(), -1)
		self._make_work_log(date=date)

		with self.assertRaises(frappe.ValidationError):
			self._make_work_log(date=date)

	def test_backdated_log_beyond_limit_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._make_work_log(date=add_days(nowdate(), -10))

	def test_item_validation(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Daily Work Log",
					"employee": self.employee,
					"date": nowdate(),
					"items": [
						{
							"task_title": "Short",
							"project": self.project,
							"description": "Too short",
							"time_spent_hours": 2,
						}
					],
				}
			).insert(ignore_permissions=True)

	def test_submit_sets_status(self):
		doc = self._make_work_log()
		doc.submit()
		self.assertEqual(doc.status, "Submitted")
		self.assertEqual(doc.docstatus, 1)

	def tearDown(self):
		frappe.db.delete(
			"Daily Work Log",
			{
				"employee": self.employee,
			},
		)
		super().tearDown()
