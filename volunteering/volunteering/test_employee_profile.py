from unittest.mock import Mock, patch

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.employee_profile import PROFILE_FIELDS, get_my_profile


class UnitTestEmployeeProfile(UnitTestCase):
	def setUp(self):
		super().setUp()
		previous = frappe.session.user
		self.addCleanup(setattr, frappe.session, "user", previous)
		frappe.session.user = "profile.employee@example.com"

	def lookup(self, doctype, filters, fields, as_dict=False):
		if doctype == "User" and filters == frappe.session.user:
			self.assertEqual(fields, ["full_name", "email", "user_type"])
			return {
				"full_name": "Profile Employee",
				"email": frappe.session.user,
				"user_type": "System User",
				"reset_password_key": "must-not-be-returned",
			}
		if doctype == "Employee" and isinstance(filters, dict):
			self.assertEqual(filters, {"user_id": frappe.session.user})
			self.assertTrue(set(fields).issubset(PROFILE_FIELDS))
			return {
				"name": "PROFILE-EMP-1",
				"employee_name": "Profile Employee",
				"reports_to": "PROFILE-MANAGER",
				"expense_approver": "approver@example.com",
				"bank_ac_no": "must-not-be-returned",
				"salary": 99999,
				"pan_number": "must-not-be-returned",
			}
		if (doctype, filters, fields) == ("Employee", "PROFILE-MANAGER", "employee_name"):
			return "Reporting Manager"
		if (doctype, filters, fields) == ("User", "approver@example.com", "full_name"):
			return "Expense Approver"
		self.fail(f"Unexpected lookup: {doctype}, {filters}, {fields}")

	def test_profile_is_session_bound_and_uses_explicit_field_allowlists(self):
		with (
			patch("frappe.db.get_value", side_effect=self.lookup) as get_value,
			patch("frappe.get_meta", return_value=Mock(has_field=lambda _field: True)),
			patch("frappe.get_doc") as get_doc,
		):
			profile = get_my_profile()
		self.assertEqual(profile["account"]["user_id"], frappe.session.user)
		self.assertEqual(profile["employee"]["name"], "PROFILE-EMP-1")
		self.assertEqual(profile["employee"]["reporting_manager_name"], "Reporting Manager")
		self.assertEqual(profile["employee"]["expense_approver_name"], "Expense Approver")
		self.assertEqual(get_value.call_count, 4)
		get_doc.assert_not_called()
		for field in ("bank_ac_no", "salary", "pan_number", "reset_password_key"):
			self.assertNotIn(field, profile["employee"])
			self.assertNotIn(field, profile["account"])

	def test_guest_is_rejected_without_profile_database_reads(self):
		frappe.session.user = "Guest"
		# Frappe may read translations when constructing a permission error;
		# those are not profile queries and should not be mocked into recursion.
		with patch("frappe.db.get_value", wraps=frappe.db.get_value) as get_value:
			with self.assertRaises(frappe.PermissionError):
				get_my_profile()
		for query in get_value.call_args_list:
			doctype = query.args[0] if query.args else query.kwargs.get("doctype")
			self.assertNotIn(doctype, ("User", "Employee"))

	def test_missing_employee_returns_own_login_details_only(self):
		with (
			patch("frappe.db.get_value", side_effect=[{"full_name": "System User"}, None]),
			patch("frappe.get_meta", return_value=Mock(has_field=lambda _field: True)),
		):
			profile = get_my_profile()
		self.assertIsNone(profile["employee"])
		self.assertEqual(profile["account"]["user_id"], frappe.session.user)

	def test_missing_user_is_rejected(self):
		with patch("frappe.db.get_value", return_value=None):
			with self.assertRaises(frappe.PermissionError):
				get_my_profile()

	def test_profile_tolerates_optional_hr_fields_not_installed(self):
		with (
			patch("frappe.db.get_value", side_effect=self.lookup) as get_value,
			patch("frappe.get_meta", return_value=Mock(has_field=lambda field: field != "grade")),
		):
			profile = get_my_profile()
		self.assertNotIn("grade", get_value.call_args_list[1].args[2])
		self.assertNotIn("grade", profile["employee"])

	def test_request_arguments_cannot_select_another_employee(self):
		# The HTTP dispatcher may discard unexpected kwargs; even then the
		# endpoint derives identity exclusively from the session.
		with (
			patch("frappe.db.get_value", side_effect=self.lookup),
			patch("frappe.get_meta", return_value=Mock(has_field=lambda _field: True)),
		):
			profile = frappe.call(get_my_profile, employee="OTHER-EMP", user="other@example.com")
		self.assertEqual(profile["employee"]["name"], "PROFILE-EMP-1")
		self.assertEqual(profile["account"]["user_id"], frappe.session.user)
