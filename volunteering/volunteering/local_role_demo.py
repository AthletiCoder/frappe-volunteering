"""Optional localhost-only project/account personas; never run during migration.

Supply a password to populate_project_account_users through ``bench execute``.
Existing users, their roles and passwords are preserved. No business documents
or global permissions are seeded. This is deliberately separate from the full
E2E seeder, which also configures HR and volunteering fixtures.
"""

from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

NEW_PERSONAS = (
	("Project creator", "demo.project.user@sevamrita.local", "Demo Project User", "Projects User"),
	("Project manager", "demo.project.manager@sevamrita.local", "Demo Project Manager", "Projects Manager"),
	("Project viewer", "demo.project.viewer@sevamrita.local", "Demo Project Viewer", "Project Viewer"),
	("Accounts operator", "demo.accounts.user@sevamrita.local", "Demo Accounts User", "Accounts User"),
	("Read-only auditor", "demo.auditor@sevamrita.local", "Demo Auditor", "Auditor"),
)
EXISTING_PERSONAS = (
	("Ordinary employee", "e2e.associate@sevamrita.local"),
	("Receipt reviewer", "e2e.receipts@sevamrita.local"),
	("Manager approval", "e2e.manager@sevamrita.local"),
	("Director approval", "e2e.director@sevamrita.local"),
	("Board-level approval", "e2e.chair@sevamrita.local"),
	("Accounts manager", "e2e.accounts@sevamrita.local"),
)


def _require_local_site():
	if frappe.local.site != "sevamrita.local":
		frappe.throw("These demo accounts may only be created on sevamrita.local.")


def describe_project_account_users():
	"""Read back actual roles, grades and module permissions without changing them."""
	_require_local_site()
	personas = [(purpose, email) for purpose, email, *_ in NEW_PERSONAS] + list(EXISTING_PERSONAS)
	results = []
	for purpose, email in personas:
		user = frappe.db.get_value("User", email, ["enabled", "user_type"], as_dict=True)
		if not user:
			continue
		employee = frappe.db.get_value(
			"Employee",
			{"user_id": email},
			["name", "grade", "reports_to", "expense_approver", "company", "department"],
			as_dict=True,
		)
		permissions = {}
		for doctype, actions in (
			("Project", ("read", "create", "write", "delete", "share")),
			("Account", ("read", "create", "write")),
			("Cost Center", ("read", "create", "write")),
			("Payment Entry", ("read", "create", "submit", "cancel")),
		):
			permissions[doctype] = {
				action: bool(frappe.has_permission(doctype, ptype=action, user=email)) for action in actions
			}
		results.append(
			{
				"purpose": purpose,
				"email": email,
				**user,
				"employee": employee,
				"roles": sorted(frappe.get_all("Has Role", filters={"parent": email}, pluck="role")),
				"module_permissions": permissions,
			}
		)
	return results


def populate_project_account_users(password: str):
	"""Create five missing representative profiles, preserving existing personas.

	All new users have Associate grade: a Projects Manager module role must not
	accidentally grant financial approval authority. Existing manager/director/
	board personas provide the separate approval hierarchy.
	"""
	_require_local_site()
	if not password:
		frappe.throw("Supply a password for the new local demo accounts.")
	manager = frappe.db.get_value(
		"Employee",
		{"user_id": "e2e.manager@sevamrita.local", "status": "Active"},
		["name", "company", "department"],
		as_dict=True,
	)
	if not manager or not manager.company or not manager.department:
		frappe.throw("An active E2E Manager with Company and Department is required.")
	if not frappe.db.exists("Employee Grade", "Associate"):
		frappe.throw("The existing Associate grade is required.")
	manager_roles = set(frappe.get_roles("e2e.manager@sevamrita.local"))
	if not {"Leave Approver", "Expense Approver"}.issubset(manager_roles):
		frappe.throw("The existing E2E Manager must already have the approver roles.")
	for _, email in EXISTING_PERSONAS:
		if not frappe.db.exists("User", email):
			frappe.throw(f"Expected existing test account is missing: {email}")
	for _, email, _, role in NEW_PERSONAS:
		if not frappe.db.exists("Role", {"name": role, "disabled": 0}):
			frappe.throw(f"Required role is missing or disabled: {role}")
		if frappe.db.exists("User", email):
			actual = set(frappe.get_all("Has Role", filters={"parent": email}, pluck="role"))
			# The installed Wiki app assigns Wiki User to every newly inserted
			# user. Preserve that site default without mistaking it for a
			# manually changed project/account persona.
			if actual - {"Wiki User"} != {"Employee", "Desk User", role}:
				frappe.throw(f"Existing demo account has different roles; left unchanged: {email}")

	created = []
	created_employees = []
	previous_mute = frappe.flags.mute_emails
	try:
		frappe.flags.mute_emails = True
		# Keep this accounts/projects-only fixture from allocating leave or
		# bootstrapping unrelated HR settings. All normal Employee validation,
		# user synchronization and reporting-tree maintenance still run.
		with patch("volunteering.volunteering.leave_setup.assign_leave_policy_to_employee"):
			for _, email, name, role in NEW_PERSONAS:
				if not frappe.db.exists("User", email):
					frappe.get_doc(
						{
							"doctype": "User",
							"email": email,
							"first_name": name,
							"enabled": 1,
							"user_type": "System User",
							"send_welcome_email": 0,
							"new_password": password,
							"roles": [{"role": value} for value in ("Employee", "Desk User", role)],
						}
					).insert(ignore_permissions=True)
					created.append(email)
				if not frappe.db.exists("Employee", {"user_id": email}):
					employee = frappe.get_doc(
						{
							"doctype": "Employee",
							"first_name": name,
							"company": manager.company,
							"department": manager.department,
							"user_id": email,
							"company_email": email,
							"status": "Active",
							"grade": "Associate",
							"reports_to": manager.name,
							"expense_approver": "e2e.manager@sevamrita.local",
							"create_user_permission": 0,
							"date_of_birth": add_days(nowdate(), -10000),
							"date_of_joining": add_days(nowdate(), -90),
							"gender": "Male",
						}
					).insert(ignore_permissions=True)
					created_employees.append(employee.name)
		result = {
			"created_users": created,
			"created_employees": created_employees,
			"personas": describe_project_account_users(),
		}
		frappe.db.commit()
		return result
	except Exception:
		frappe.db.rollback()
		raise
	finally:
		frappe.flags.mute_emails = previous_mute
