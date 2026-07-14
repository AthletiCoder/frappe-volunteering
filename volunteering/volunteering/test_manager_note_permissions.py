# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from volunteering.volunteering.manager_note_permissions import (
	get_permission_query_conditions,
	has_permission,
	is_in_manager_hierarchy,
)

GRAND_MANAGER_EMAIL = "volunteering_test_grandmanager@example.com"
MANAGER_EMAIL = "volunteering_test_manager@example.com"
REPORT_EMAIL = "volunteering_test_report@example.com"


class IntegrationTestManagerNotePermissions(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.grand_manager = self._ensure_employee("Test Grand Manager", GRAND_MANAGER_EMAIL)
		self.manager = self._ensure_employee("Test Manager", MANAGER_EMAIL)
		self.report = self._ensure_employee("Test Report", REPORT_EMAIL)
		frappe.db.set_value("Employee", self.manager, "reports_to", self.grand_manager)
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

	def _note_doc(self):
		return frappe._dict({"doctype": "Manager Note", "employee": self.report})

	def test_hierarchy_detection(self):
		self.assertTrue(is_in_manager_hierarchy(self.manager, self.report))
		self.assertTrue(is_in_manager_hierarchy(self.grand_manager, self.report))
		self.assertFalse(is_in_manager_hierarchy(self.report, self.manager))

	def test_direct_manager_can_read(self):
		self.assertTrue(has_permission(self._note_doc(), "read", MANAGER_EMAIL))

	def test_skip_level_manager_can_read(self):
		self.assertTrue(has_permission(self._note_doc(), "read", GRAND_MANAGER_EMAIL))

	def test_employee_cannot_read_own_note(self):
		self.assertFalse(has_permission(self._note_doc(), "read", REPORT_EMAIL))

	def test_manager_cannot_edit_or_delete(self):
		self.assertFalse(has_permission(self._note_doc(), "write", MANAGER_EMAIL))
		self.assertFalse(has_permission(self._note_doc(), "delete", MANAGER_EMAIL))

	def test_employee_query_conditions_hide_all(self):
		condition = get_permission_query_conditions(REPORT_EMAIL)
		self.assertEqual(condition, "1=0")

	def test_admin_sees_all(self):
		self.assertEqual(get_permission_query_conditions("Administrator"), "")

	def test_note_is_append_only_with_audit_fields(self):
		note = frappe.get_doc(
			{
				"doctype": "Manager Note",
				"employee": self.report,
				"note_date": nowdate(),
				"note_type": "Appreciation",
				"content": "Excellent ownership shown.",
			}
		)
		note.insert(ignore_permissions=True)
		self.assertTrue(note.authored_by)
		self.assertTrue(note.authored_on)
		note.delete(ignore_permissions=True)
