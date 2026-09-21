"""Role-separated employee and login administration in the Home portal."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from volunteering.volunteering.accounting_test_utils import (
	get_or_create_user,
	mute_accounting_test_emails,
)
from volunteering.volunteering.people_management import (
	get_hr_management_workspace,
	get_managed_employee,
	get_managed_user,
	get_system_management_workspace,
	save_managed_employee,
	save_managed_user,
)


class IntegrationTestPeopleManagement(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.emails = mute_accounting_test_emails()
		cls.hr = get_or_create_user("people-home-hr@example.com", ["HR Manager"], "People HR")
		cls.system = get_or_create_user("people-home-system@example.com", ["System Manager"], "People System")
		cls.employee = get_or_create_user("people-home-ordinary@example.com", ["Employee"], "Ordinary")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		cls.emails.close()
		frappe.flags.mute_emails = False
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _new_user(self):
		return {
			"email": f"people-home-{frappe.generate_hash(length=8)}@example.com",
			"first_name": "Portal",
			"last_name": "Employee",
			"enabled": True,
			"user_type": "System User",
			"send_welcome_email": False,
			"role_mode": "roles",
			"roles": ["Employee"],
			"role_profiles": [],
		}

	def _new_employee(self, user_id):
		return {
			"first_name": "Portal",
			"last_name": "Employee",
			"gender": frappe.get_all("Gender", pluck="name", limit=1)[0],
			"date_of_birth": add_days(nowdate(), -9000),
			"date_of_joining": add_days(nowdate(), -30),
			"status": "Active",
			"user_id": user_id,
		}

	def test_roles_can_manage_only_their_own_records(self):
		frappe.set_user(self.employee)
		with self.assertRaises(frappe.PermissionError):
			get_hr_management_workspace()
		with self.assertRaises(frappe.PermissionError):
			get_system_management_workspace()

		frappe.set_user(self.hr)
		self.assertTrue(get_hr_management_workspace()["can_manage"])
		with self.assertRaises(frappe.PermissionError):
			get_system_management_workspace()
		with self.assertRaises(frappe.PermissionError):
			save_managed_user(self._new_user())

		frappe.set_user(self.system)
		self.assertTrue(get_system_management_workspace()["can_manage"])
		with self.assertRaises(frappe.PermissionError):
			get_hr_management_workspace()
		with self.assertRaises(frappe.PermissionError):
			save_managed_employee(self._new_employee(""))

	def test_system_creates_user_and_hr_links_employee(self):
		frappe.set_user(self.system)
		user = save_managed_user(self._new_user())["user"]
		self.assertEqual(user["user_type"], "System User")
		# ERPNext removes Employee on an unlinked User and adds it when HR links
		# an Employee record. The login account and employee lifecycle stay separate.
		self.assertNotIn("Employee", user["roles"])

		frappe.set_user(self.hr)
		employee = save_managed_employee(self._new_employee(user["name"]))["employee"]
		self.assertEqual(employee["user_id"], user["name"])
		self.assertEqual(get_managed_employee(employee["name"])["name"], employee["name"])
		self.assertIn("Employee", frappe.get_roles(user["name"]))
		updated_employee = save_managed_employee(
			{**employee, "first_name": "Updated"},
			name=employee["name"],
			expected_modified=employee["modified"],
		)["employee"]
		self.assertEqual(updated_employee["employee_name"], "Updated Employee")
		with self.assertRaisesRegex(frappe.ValidationError, "already linked"):
			save_managed_employee(self._new_employee(user["name"]))

		frappe.set_user(self.system)
		self.assertEqual(get_managed_user(user["name"])["employee"]["name"], employee["name"])
		current = get_managed_user(user["name"])
		saved = save_managed_user(
			{
				"first_name": current["first_name"],
				"last_name": current["last_name"],
				"enabled": True,
				"user_type": "System User",
				"role_mode": "roles",
				"roles": [],
			},
			name=user["name"],
			expected_modified=current["modified"],
		)["user"]
		self.assertIn("Employee", saved["roles"])
		self.assertIn("Employee", frappe.get_roles(user["name"]))
		with self.assertRaisesRegex(frappe.ValidationError, "includes the Employee role"):
			save_managed_user(
				{
					"first_name": current["first_name"],
					"last_name": current["last_name"],
					"enabled": True,
					"user_type": "System User",
					"role_mode": "profiles",
					"role_profiles": [],
				},
				name=user["name"],
			)

	def test_stale_edits_and_self_lockout_are_rejected(self):
		frappe.set_user(self.system)
		created = save_managed_user(self._new_user())["user"]
		with self.assertRaisesRegex(frappe.ValidationError, "changed after you opened"):
			save_managed_user(
				{
					**self._new_user(),
					"first_name": "Updated",
				},
				name=created["name"],
				expected_modified="old-modified-value",
			)
		self_record = get_managed_user(self.system)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot disable your own"):
			save_managed_user(
				{
					"first_name": self_record["first_name"],
					"last_name": self_record["last_name"],
					"enabled": False,
					"user_type": "System User",
					"role_mode": "roles",
					"roles": ["System Manager"],
				},
				name=self.system,
				expected_modified=self_record["modified"],
			)

	def test_system_manager_can_disable_another_login(self):
		frappe.set_user(self.system)
		details = self._new_user()
		details["roles"] = ["Projects User"]
		created = save_managed_user(details)["user"]
		details["enabled"] = False
		updated = save_managed_user(
			details,
			name=created["name"],
			expected_modified=created["modified"],
		)["user"]
		self.assertFalse(updated["enabled"])
		self.assertFalse(frappe.db.get_value("User", created["name"], "enabled"))

	def test_role_profile_assignment_uses_frappes_effective_roles(self):
		frappe.set_user("Administrator")
		profile_name = f"People Portal {frappe.generate_hash(length=8)}"
		frappe.get_doc(
			{"doctype": "Role Profile", "role_profile": profile_name, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		frappe.set_user(self.system)
		details = self._new_user()
		details.update({"role_mode": "profiles", "roles": [], "role_profiles": [profile_name]})
		user = save_managed_user(details)["user"]
		self.assertEqual(user["role_profiles"], [profile_name])
		self.assertNotIn("Employee", user["roles"])
