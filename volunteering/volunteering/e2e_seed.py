# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Seed dedicated E2E personas on a local site (sevamrita.local).

Run:
  bench --site sevamrita.local execute volunteering.volunteering.e2e_seed.seed_e2e_personas

Passwords are NOT stored here — set them via env E2E_PASSWORD (default E2eTestPass!26)
and mirror into apps/volunteering/e2e/.env for Playwright.
"""

from __future__ import annotations

import os

import frappe
from frappe.utils.password import update_password

from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department,
	get_or_create_employee,
)


def _get_or_create_user(email: str, roles: list[str], first_name: str, password: str) -> str:
	"""Like accounting_test_utils.get_or_create_user, but with a strong password."""
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
				"new_password": password,
			}
		)
		user.insert(ignore_permissions=True)

	existing_roles = {row.role for row in user.roles}
	for role in roles:
		if role not in existing_roles:
			user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	_set_password(email, password)
	return email

# Fixed local-only emails (safe; no real mailbox).
PERSONAS = {
	"employee": {
		"email": "e2e.employee@sevamrita.local",
		"first_name": "E2E Employee A",
		"roles": ["Employee"],
		"designation": "Associate",
		"employee_name": "E2E Employee A",
	},
	"employee_b": {
		"email": "e2e.employee.b@sevamrita.local",
		"first_name": "E2E Employee B",
		"roles": ["Employee"],
		"designation": "Associate",
		"employee_name": "E2E Employee B",
	},
	"associate": {
		"email": "e2e.associate@sevamrita.local",
		"first_name": "E2E Associate",
		"roles": ["Employee"],
		"designation": "Associate",
		"employee_name": "E2E Associate",
	},
	"manager": {
		"email": "e2e.manager@sevamrita.local",
		"first_name": "E2E Manager",
		"roles": ["Employee"],
		"designation": "Manager",
		"employee_name": "E2E Manager",
	},
	"director": {
		"email": "e2e.director@sevamrita.local",
		"first_name": "E2E Director",
		"roles": ["Employee"],
		"designation": "Director",
		"employee_name": "E2E Director",
	},
	"chair": {
		"email": "e2e.chair@sevamrita.local",
		"first_name": "E2E Board Chair",
		"roles": ["Employee", "NGO Board Chairperson"],
		"designation": "Board of Directors",
		"employee_name": "E2E Board Chair",
	},
	"hr": {
		"email": "e2e.hr@sevamrita.local",
		"first_name": "E2E HR",
		"roles": ["HR Manager", "Employee"],
		"designation": "Manager",
		"employee_name": "E2E HR",
	},
	"accounts": {
		"email": "e2e.accounts@sevamrita.local",
		"first_name": "E2E Accounts",
		"roles": ["Accounts Manager", "Accounts User", "Employee"],
		"designation": "Manager",
		"employee_name": "E2E Accounts",
	},
	"unpaid": {
		"email": "e2e.unpaid@sevamrita.local",
		"first_name": "E2E Unpaid",
		"roles": ["Employee"],
		"designation": "Associate",
		"employee_name": "E2E Unpaid",
		"employment_type": "Unpaid",
	},
}


def _ensure_designations():
	for name in ("Associate", "Manager", "Director", "Board of Directors"):
		if not frappe.db.exists("Designation", name):
			frappe.get_doc(
				{"doctype": "Designation", "designation_name": name}
			).insert(ignore_permissions=True)


def _ensure_employment_type(name: str):
	if not name or frappe.db.exists("Employment Type", name):
		return
	doc = frappe.new_doc("Employment Type")
	for field in ("employee_type_name", "employment_type"):
		if doc.meta.has_field(field):
			doc.set(field, name)
			break
	else:
		# Fallback: naming often uses employee_type_name as title
		doc.set("employee_type_name", name)
	doc.insert(ignore_permissions=True)


def _set_password(email: str, password: str):
	update_password(email, password)
	# Keep User.new_password clear; update_password is authoritative
	frappe.db.set_value("User", email, "enabled", 1)


def _ensure_role(role_name: str):
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc(
			{"doctype": "Role", "role_name": role_name, "desk_access": 1}
		).insert(ignore_permissions=True)


def seed_e2e_personas(password: str | None = None) -> dict:
	"""Create/update E2E users, employees, designations, and Reports To chain.

	Returns a summary dict of persona → {email, employee}.
	"""
	password = password or os.environ.get("E2E_PASSWORD") or "E2eTestPass!26"
	frappe.flags.mute_emails = True
	_ensure_designations()

	# Ensure custom roles used by accounting tests exist
	for role in ("NGO Board Chairperson", "NGO Board Member"):
		_ensure_role(role)

	if PERSONAS["unpaid"].get("employment_type"):
		try:
			_ensure_employment_type(PERSONAS["unpaid"]["employment_type"])
		except Exception as exc:
			# Non-fatal: unpaid type may already exist under another name
			frappe.log_error(f"E2E unpaid employment type: {exc}")

	department = get_or_create_department("E2E Operations")

	created: dict[str, dict] = {}
	employees: dict[str, str] = {}

	for key, spec in PERSONAS.items():
		email = _get_or_create_user(spec["email"], spec["roles"], spec["first_name"], password)
		emp = get_or_create_employee(email, department, spec["employee_name"])
		employees[key] = emp
		updates = {"designation": spec["designation"], "status": "Active"}
		if spec.get("employment_type") and frappe.db.exists(
			"Employment Type", spec["employment_type"]
		):
			updates["employment_type"] = spec["employment_type"]
		frappe.db.set_value("Employee", emp, updates)
		created[key] = {"email": email, "employee": emp}

	# Chain: employee/associate/employee_b/unpaid → manager → director → chair
	manager_emp = employees["manager"]
	director_emp = employees["director"]
	chair_emp = employees["chair"]

	for key in ("employee", "employee_b", "associate", "unpaid"):
		frappe.db.set_value(
			"Employee",
			employees[key],
			{
				"reports_to": manager_emp,
				"leave_approver": PERSONAS["manager"]["email"],
			},
		)

	frappe.db.set_value(
		"Employee",
		manager_emp,
		{
			"reports_to": director_emp,
			"leave_approver": PERSONAS["director"]["email"],
		},
	)
	frappe.db.set_value(
		"Employee",
		director_emp,
		{
			"reports_to": chair_emp,
			"leave_approver": PERSONAS["chair"]["email"],
		},
	)
	frappe.db.set_value(
		"Employee",
		chair_emp,
		{"reports_to": None, "leave_approver": PERSONAS["chair"]["email"]},
	)
	# HR / Accounts report to director for org chart consistency
	for key in ("hr", "accounts"):
		frappe.db.set_value(
			"Employee",
			employees[key],
			{
				"reports_to": director_emp,
				"leave_approver": PERSONAS["director"]["email"],
			},
		)

	frappe.db.commit()
	return created


def list_e2e_personas() -> dict:
	"""Return current emails/employees for the E2E cast (no writes)."""
	out = {}
	for key, spec in PERSONAS.items():
		emp = frappe.db.get_value("Employee", {"user_id": spec["email"]}, "name")
		out[key] = {
			"email": spec["email"],
			"employee": emp,
			"exists_user": bool(frappe.db.exists("User", spec["email"])),
		}
	return out
