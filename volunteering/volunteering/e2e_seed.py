# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Seed dedicated E2E personas on a local site (sevamrita.local).

Aligned with docs/role-architecture.md:
  Role = module access, Grade = approval authority, Designation = job title.

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
	ensure_employee_grade,
	get_or_create_department,
	get_or_create_employee,
	set_employee_grade,
)
from volunteering.volunteering.authority import BOARD_OF_DIRECTORS


def _get_or_create_user(email: str, roles: list[str], first_name: str, password: str) -> str:
	"""Create/update user with roles; strip obsolete board roles when not requested."""
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

	desired = set(roles)
	# Pin E2E users to the exact role set from PERSONAS (drop legacy board roles).
	user.set("roles", [])
	for role in roles:
		_ensure_role(role, desk_access=0 if role == "NGO Member" else 1)
		user.append("roles", {"role": role})
	# Always keep Desk User for staff (Frappe adds it often); volunteer stays portal-only
	if "NGO Member" not in desired and "Desk User" not in desired:
		user.append("roles", {"role": "Desk User"})
	user.save(ignore_permissions=True)
	_set_password(email, password)
	return email


# Fixed local-only emails (safe; no real mailbox).
# grade = authority band; designation = job title only.
PERSONAS = {
	"employee": {
		"email": "e2e.employee@sevamrita.local",
		"first_name": "E2E Employee A",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Program Officer",
		"employee_name": "E2E Employee A",
	},
	"employee_b": {
		"email": "e2e.employee.b@sevamrita.local",
		"first_name": "E2E Employee B",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Program Officer",
		"employee_name": "E2E Employee B",
	},
	"associate": {
		"email": "e2e.associate@sevamrita.local",
		"first_name": "E2E Associate",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Associate",
		"employee_name": "E2E Associate",
	},
	"manager": {
		"email": "e2e.manager@sevamrita.local",
		"first_name": "E2E Manager",
		"roles": ["Employee", "Leave Approver", "Expense Approver"],
		"grade": "Manager",
		"designation": "Operations Manager",
		"employee_name": "E2E Manager",
	},
	"director": {
		"email": "e2e.director@sevamrita.local",
		"first_name": "E2E Director",
		"roles": ["Employee", "Leave Approver", "Expense Approver"],
		"grade": "Director",
		"designation": "Director",
		"employee_name": "E2E Director",
	},
	"chair": {
		"email": "e2e.chair@sevamrita.local",
		"first_name": "E2E Board Chair",
		"roles": ["Employee", "Accounts User"],
		"grade": BOARD_OF_DIRECTORS,
		"designation": "Chairperson",
		"employee_name": "E2E Board Chair",
	},
	"hr": {
		"email": "e2e.hr@sevamrita.local",
		"first_name": "E2E HR",
		"roles": ["HR Manager", "Employee"],
		"grade": "Manager",
		"designation": "HR Manager",
		"employee_name": "E2E HR",
	},
	"accounts": {
		"email": "e2e.accounts@sevamrita.local",
		"first_name": "E2E Accounts",
		"roles": ["Accounts Manager", "Accounts User", "Employee"],
		"grade": "Manager",
		"designation": "Accounts Manager",
		"employee_name": "E2E Accounts",
	},
	"unpaid": {
		"email": "e2e.unpaid@sevamrita.local",
		"first_name": "E2E Unpaid",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Volunteer Staff",
		"employee_name": "E2E Unpaid",
		"employment_type": "Unpaid",
	},
	"coordinator": {
		"email": "e2e.coordinator@sevamrita.local",
		"first_name": "E2E Coordinator",
		"roles": ["NGO Coordinator", "Employee"],
		"grade": "Manager",
		"designation": "NGO Coordinator",
		"employee_name": "E2E Coordinator",
	},
	# Volunteer: NGO Member only — no Employee record
	"volunteer": {
		"email": "e2e.volunteer@sevamrita.local",
		"first_name": "E2E Volunteer",
		"roles": ["NGO Member"],
		"no_employee": True,
	},
}


def _ensure_designations():
	for name in (
		"Program Officer",
		"Associate",
		"Operations Manager",
		"Director",
		"Chairperson",
		"HR Manager",
		"Accounts Manager",
		"Volunteer Staff",
		"NGO Coordinator",
	):
		if not frappe.db.exists("Designation", name):
			frappe.get_doc(
				{"doctype": "Designation", "designation_name": name}
			).insert(ignore_permissions=True)


def _ensure_grades():
	for grade in (
		"Associate",
		"Manager",
		"Director",
		BOARD_OF_DIRECTORS,
		"Vice President",
		"President",
		"CEO",
		"Executive Board",
	):
		ensure_employee_grade(grade)


def _ensure_employment_type(name: str):
	if not name or frappe.db.exists("Employment Type", name):
		return
	doc = frappe.new_doc("Employment Type")
	for field in ("employee_type_name", "employment_type"):
		if doc.meta.has_field(field):
			doc.set(field, name)
			break
	else:
		doc.set("employee_type_name", name)
	doc.insert(ignore_permissions=True)


def _set_password(email: str, password: str):
	update_password(email, password)
	frappe.db.set_value("User", email, "enabled", 1)


def _ensure_role(role_name: str, desk_access: int = 1):
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": desk_access,
			}
		).insert(ignore_permissions=True)


def _ensure_custom_docperm(doctype: str, role: str, **flags):
	"""Grant role doctype access for E2E (Custom DocPerm survives migrate)."""
	if frappe.db.exists(
		"Custom DocPerm",
		{"parent": doctype, "parenttype": "DocType", "role": role, "permlevel": 0},
	):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			**flags,
		}
	)
	doc.insert(ignore_permissions=True)


def _ensure_e2e_doctype_permissions():
	"""Employee self-service + manager notes need base DocPerm before custom hooks."""
	if frappe.db.exists("DocType", "Leave Application"):
		_ensure_custom_docperm(
			"Leave Application",
			"Employee",
			read=1,
			write=1,
			create=1,
			submit=1,
			cancel=1,
			email=1,
			print=1,
			export=1,
			report=1,
		)
	if frappe.db.exists("DocType", "Manager Note"):
		_ensure_custom_docperm(
			"Manager Note",
			"Employee",
			read=1,
			create=1,
			email=1,
			print=1,
			export=1,
			report=1,
		)
	if frappe.db.exists("DocType", "Employee Advance"):
		_ensure_custom_docperm(
			"Employee Advance",
			"Accounts Manager",
			read=1,
			write=1,
			create=1,
			submit=1,
			cancel=1,
			amend=1,
			print=1,
			email=1,
			export=1,
			report=1,
		)
		_ensure_custom_docperm(
			"Employee Advance",
			"Employee",
			read=1,
			write=1,
			create=1,
			submit=1,
			cancel=1,
			print=1,
			email=1,
		)


def seed_e2e_personas(password: str | None = None) -> dict:
	"""Create/update E2E users, employees, grades, and Reports To chain.

	Returns a summary dict of persona → {email, employee}.
	"""
	password = password or os.environ.get("E2E_PASSWORD") or "E2eTestPass!26"
	frappe.flags.mute_emails = True
	_ensure_designations()
	_ensure_grades()
	_ensure_e2e_doctype_permissions()

	for role in (
		"NGO Member",
		"NGO Coordinator",
		"NGO Admin",
		"Leave Approver",
		"Expense Approver",
	):
		_ensure_role(role, desk_access=0 if role == "NGO Member" else 1)

	if PERSONAS["unpaid"].get("employment_type"):
		try:
			_ensure_employment_type(PERSONAS["unpaid"]["employment_type"])
		except Exception as exc:
			frappe.log_error(f"E2E unpaid employment type: {exc}")

	department = get_or_create_department("E2E Operations")

	created: dict[str, dict] = {}
	employees: dict[str, str] = {}

	for key, spec in PERSONAS.items():
		email = _get_or_create_user(
			spec["email"], spec["roles"], spec["first_name"], password
		)
		if spec.get("no_employee"):
			created[key] = {"email": email, "employee": None}
			continue

		emp = get_or_create_employee(email, department, spec["employee_name"])
		employees[key] = emp
		set_employee_grade(emp, spec["grade"])
		updates = {"designation": spec["designation"], "status": "Active"}
		if spec.get("employment_type") and frappe.db.exists(
			"Employment Type", spec["employment_type"]
		):
			updates["employment_type"] = spec["employment_type"]
		frappe.db.set_value("Employee", emp, updates)
		created[key] = {"email": email, "employee": emp}

	manager_emp = employees["manager"]
	director_emp = employees["director"]
	chair_emp = employees["chair"]

	# Manager heads E2E Operations department
	frappe.db.set_value("Department", department, "department_head", PERSONAS["manager"]["email"])

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
	for key in ("hr", "accounts", "coordinator"):
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
		emp = None
		if not spec.get("no_employee"):
			emp = frappe.db.get_value("Employee", {"user_id": spec["email"]}, "name")
		out[key] = {
			"email": spec["email"],
			"employee": emp,
			"exists_user": bool(frappe.db.exists("User", spec["email"])),
			"grade": spec.get("grade"),
		}
	return out
