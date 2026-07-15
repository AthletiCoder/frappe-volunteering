# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from volunteering.volunteering.leave_policy import validate_leave_application
from volunteering.volunteering.test_utils import (
	ensure_employee_holiday_list,
	get_or_create_test_employee,
)


class IntegrationTestLeavePolicy(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.employee = self._get_or_create_employee()
		ensure_employee_holiday_list(self.employee)
		self.leave_type = self._get_or_create_leave_type("Privilege Leave")
		self._ensure_leave_allocation(self.leave_type)

	def tearDown(self):
		frappe.db.delete(
			"Leave Application",
			{"employee": self.employee, "leave_type": self.leave_type},
		)
		super().tearDown()

	def _get_or_create_employee(self):
		return get_or_create_test_employee()

	def _get_or_create_leave_type(self, name):
		if frappe.db.exists("Leave Type", name):
			return name

		return frappe.get_doc(
			{
				"doctype": "Leave Type",
				"leave_type_name": name,
				"allow_negative": 1,
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
				"new_leaves_allocated": 30,
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
				"leave_category": kwargs.get("leave_category", "Normal"),
				"from_date": kwargs.get("from_date", add_days(nowdate(), 5)),
				"to_date": kwargs.get("to_date", add_days(nowdate(), 5)),
				"description": kwargs.get("description", ""),
				"leave_approver": kwargs.get("leave_approver"),
				"status": "Open",
			}
		)

	def test_emergency_leave_too_far_backdated(self):
		from unittest.mock import patch

		doc = self._make_leave_application(
			leave_category="Emergency",
			from_date=add_days(nowdate(), -5),
			to_date=add_days(nowdate(), -5),
		)
		# Simulate a regular employee (tests run as Administrator, who may backfill)
		with patch("volunteering.volunteering.leave_policy._is_hr_user", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				validate_leave_application(doc)

	def test_emergency_leave_cannot_exceed_three_days(self):
		doc = self._make_leave_application(
			leave_category="Emergency",
			from_date=nowdate(),
			to_date=add_days(nowdate(), 3),
		)
		with self.assertRaises(frappe.ValidationError):
			validate_leave_application(doc)

	def test_emergency_leave_three_days_allowed(self):
		doc = self._make_leave_application(
			leave_category="Emergency",
			from_date=nowdate(),
			to_date=add_days(nowdate(), 2),
		)
		validate_leave_application(doc)

	def test_normal_leave_requires_n_day_notice(self):
		# 3-day leave starting in 1 day should fail
		doc = self._make_leave_application(
			leave_category="Normal",
			from_date=add_days(nowdate(), 1),
			to_date=add_days(nowdate(), 3),
		)
		with self.assertRaises(frappe.ValidationError):
			validate_leave_application(doc)

	def test_normal_leave_with_sufficient_notice(self):
		doc = self._make_leave_application(
			leave_category="Normal",
			from_date=add_days(nowdate(), 5),
			to_date=add_days(nowdate(), 7),
		)
		validate_leave_application(doc)

	def test_long_leave_requires_director_approver(self):
		# Use a wide span so leave days stay above 7 even after holiday exclusion
		doc = self._make_leave_application(
			leave_category="Normal",
			from_date=add_days(nowdate(), 30),
			to_date=add_days(nowdate(), 50),
			leave_approver=None,
		)
		with self.assertRaises(frappe.ValidationError):
			validate_leave_application(doc)

	def test_sets_default_leave_type(self):
		doc = self._make_leave_application(leave_type="")
		doc.from_date = add_days(nowdate(), 5)
		doc.to_date = add_days(nowdate(), 5)
		validate_leave_application(doc)
		self.assertEqual(doc.leave_type, "Privilege Leave")
