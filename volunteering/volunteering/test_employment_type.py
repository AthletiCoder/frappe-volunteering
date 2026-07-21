# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.employment_type import (
	UNPAID_EMPLOYMENT_TYPE,
	ensure_employment_type,
	is_payroll_employee,
	is_unpaid_employee,
)
from volunteering.volunteering.test_utils import get_or_create_test_employee


class IntegrationTestEmploymentType(IntegrationTestCase):
	def test_ensure_unpaid_employment_type(self):
		name = ensure_employment_type()
		self.assertEqual(name, UNPAID_EMPLOYMENT_TYPE)
		self.assertTrue(frappe.db.exists("Employment Type", UNPAID_EMPLOYMENT_TYPE))

	def test_is_unpaid_employee_helper(self):
		employee = get_or_create_test_employee()
		previous = frappe.db.get_value("Employee", employee, "employment_type")
		ensure_employment_type()
		frappe.db.set_value("Employee", employee, "employment_type", UNPAID_EMPLOYMENT_TYPE)
		try:
			self.assertTrue(is_unpaid_employee(employee))
			self.assertFalse(is_payroll_employee(employee))
		finally:
			frappe.db.set_value("Employee", employee, "employment_type", previous)
