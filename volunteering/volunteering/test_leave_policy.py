# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from volunteering.volunteering.leave_policy import validate_leave_application


class IntegrationTestLeavePolicy(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.employee = self._get_or_create_employee()
		self.leave_type = self._get_or_create_leave_type("Privilege Leave")
		self._ensure_leave_allocation(self.leave_type)

	def tearDown(self):
		frappe.db.delete(
			"Leave Application",
			{"employee": self.employee, "leave_type": self.leave_type},
		)
		super().tearDown()

	def _get_or_create_employee(self):
		employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
		if employee:
			return employee

		company = frappe.db.get_value("Company", {}, "name")
		return frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "Leave Policy",
				"company": company,
				"status": "Active",
				"date_of_joining": add_days(nowdate(), -90),
				"gender": "Male",
			}
		).insert(ignore_permissions=True).name

	def _get_or_create_leave_type(self, name):
		if frappe.db.exists("Leave Type", name):
			return name

		return frappe.get_doc(
			{
				"doctype": "Leave Type",
				"leave_type_name": name,
			}
		).insert(ignore_permissions=True).name

	def _ensure_leave_allocation(self, leave_type):
		existing = frappe.db.exists(
			"Leave Allocation",
			{
				"employee": self.employee,
				"leave_type": leave_type,
				"docstatus": 1,
				"from_date": ["<=", nowdate()],
				"to_date": [">=", nowdate()],
			},
		)
		if existing:
			return

		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": self.employee,
				"leave_type": leave_type,
				"from_date": add_days(nowdate(), -30),
				"to_date": add_days(nowdate(), 365),
				"new_leaves_allocated": 60,
			}
		)
		allocation.insert(ignore_permissions=True)
		allocation.submit()

	def _make_leave_application(self, **kwargs):
		return frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": self.employee,
				"leave_type": kwargs.get("leave_type", self.leave_type),
				"leave_category": kwargs.get("leave_category", "Planned"),
				"from_date": kwargs.get("from_date", add_days(nowdate(), 20)),
				"to_date": kwargs.get("to_date", add_days(nowdate(), 20)),
				"description": kwargs.get("description", ""),
				"status": "Open",
			}
		)

	def test_emergency_leave_cannot_be_backdated(self):
		doc = self._make_leave_application(
			leave_category="Emergency",
			from_date=add_days(nowdate(), -1),
			to_date=add_days(nowdate(), -1),
		)

		with self.assertRaises(frappe.ValidationError):
			validate_leave_application(doc)

	def test_emergency_leave_cannot_exceed_two_days(self):
		doc = self._make_leave_application(
			leave_category="Emergency",
			from_date=nowdate(),
			to_date=add_days(nowdate(), 2),
		)

		with self.assertRaises(frappe.ValidationError):
			validate_leave_application(doc)

	def test_sick_leave_cannot_be_backdated(self):
		doc = self._make_leave_application(
			leave_category="Sick",
			from_date=add_days(nowdate(), -1),
			to_date=add_days(nowdate(), -1),
		)

		with self.assertRaises(frappe.ValidationError):
			validate_leave_application(doc)

	def test_sick_leave_allows_more_than_two_days(self):
		doc = self._make_leave_application(
			leave_category="Sick",
			from_date=nowdate(),
			to_date=add_days(nowdate(), 4),
		)

		validate_leave_application(doc)

	def test_planned_leave_cannot_be_backdated(self):
		doc = self._make_leave_application(
			leave_category="Planned",
			from_date=add_days(nowdate(), -1),
			to_date=add_days(nowdate(), -1),
		)

		with self.assertRaises(frappe.ValidationError):
			validate_leave_application(doc)

	def test_planned_leave_within_14_days_requires_justification(self):
		doc = self._make_leave_application(
			leave_category="Planned",
			from_date=add_days(nowdate(), 7),
			to_date=add_days(nowdate(), 7),
			description="Too short",
		)

		with self.assertRaises(frappe.ValidationError):
			validate_leave_application(doc)

	def test_planned_leave_within_14_days_allowed_with_justification(self):
		doc = self._make_leave_application(
			leave_category="Planned",
			from_date=add_days(nowdate(), 7),
			to_date=add_days(nowdate(), 7),
			description="Urgent family commitment requiring leave next week.",
		)

		validate_leave_application(doc)

	def test_planned_leave_after_14_days_without_justification(self):
		doc = self._make_leave_application(
			leave_category="Planned",
			from_date=add_days(nowdate(), 20),
			to_date=add_days(nowdate(), 20),
			description="",
		)

		validate_leave_application(doc)

	def test_sets_default_leave_type(self):
		doc = self._make_leave_application(leave_type="")
		validate_leave_application(doc)
		self.assertEqual(doc.leave_type, "Privilege Leave")
