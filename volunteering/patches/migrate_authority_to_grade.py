"""Move approve/advance authority from Designation + Board roles to Employee Grade.

Board / Department Head *roles* are left in place; `remove_obsolete_board_roles`
deletes them once this has run and the dual-path code has been verified.
"""

from __future__ import annotations

import frappe

from volunteering.volunteering.accounting_setup import (
	ensure_designation_limits,
	ensure_employee_grades,
)
from volunteering.volunteering.authority import (
	BOARD_OF_DIRECTORS,
	EXECUTIVE_BOARD,
	LEGACY_BOARD_MEMBER_ROLES,
	LEGACY_CHAIR_ROLES,
	LEGACY_ROLE_DEPT_HEAD,
)
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	DEFAULT_GRADE_LIMITS,
)

GRADE_NAMES = {row[0] for row in DEFAULT_GRADE_LIMITS}
COORDINATOR_ROLE = "NGO Coordinator"
ADMIN_ROLES = {"NGO Admin", "System Manager"}


def execute():
	if not frappe.db.exists("DocType", "Employee Grade"):
		return

	ensure_employee_grades()
	_copy_designation_to_grade()
	_grade_from_role(LEGACY_CHAIR_ROLES, BOARD_OF_DIRECTORS, overwrite=True)
	_grade_from_role(LEGACY_BOARD_MEMBER_ROLES, EXECUTIVE_BOARD, overwrite=False)
	_keep_department_heads_working()
	_grades_for_existing_limit_rows()
	ensure_designation_limits()
	_update_settings()

	frappe.clear_cache(doctype="Employee")
	frappe.clear_cache(doctype="Volunteering Accounting Settings")
	frappe.clear_cache(doctype="Approval and Advance Limits")


def _copy_designation_to_grade():
	"""Designation used to double as the approval band; keep those bands."""
	if not frappe.db.has_column("Employee", "grade"):
		return

	for employee in frappe.get_all(
		"Employee",
		filters={"designation": ["in", sorted(GRADE_NAMES)]},
		fields=["name", "designation", "grade"],
	):
		if employee.grade:
			continue
		frappe.db.set_value(
			"Employee", employee.name, "grade", employee.designation, update_modified=False
		)


def _grade_from_role(roles, grade, overwrite):
	if not frappe.db.has_column("Employee", "grade"):
		return

	for user in _users_with_roles(roles):
		employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if not employee:
			continue
		current = frappe.db.get_value("Employee", employee, "grade")
		if current and not overwrite:
			continue
		if current == grade:
			continue
		frappe.db.set_value("Employee", employee, "grade", grade, update_modified=False)


def _keep_department_heads_working():
	"""Dept Head role users who head no department keep org-wide ops access."""
	for user in _users_with_roles({LEGACY_ROLE_DEPT_HEAD}):
		if frappe.db.exists("Department", {"department_head": user}):
			continue
		roles = set(frappe.get_roles(user))
		if roles & ADMIN_ROLES or COORDINATOR_ROLE in roles:
			continue
		if not frappe.db.exists("Role", COORDINATOR_ROLE):
			continue
		user_doc = frappe.get_doc("User", user)
		user_doc.append("roles", {"role": COORDINATOR_ROLE})
		user_doc.save(ignore_permissions=True)


def _grades_for_existing_limit_rows():
	"""Configured rows hold Designation names; the field now links Employee Grade."""
	if not frappe.db.exists("DocType", "Approval and Advance Limits"):
		return

	for row in frappe.get_all(
		"Designation Approval Limit",
		filters={"parenttype": "Approval and Advance Limits"},
		pluck="designation",
	):
		if not row or frappe.db.exists("Employee Grade", row):
			continue
		frappe.get_doc({"doctype": "Employee Grade", "__newname": row}).insert(
			ignore_permissions=True
		)


def _users_with_roles(roles):
	existing = [role for role in roles if frappe.db.exists("Role", role)]
	if not existing:
		return []
	return frappe.get_all(
		"Has Role",
		filters={"role": ["in", existing], "parenttype": "User", "parent": ["!=", "Guest"]},
		pluck="parent",
		distinct=True,
	)


def _update_settings():
	if not frappe.db.exists("DocType", "Volunteering Accounting Settings"):
		return

	settings = frappe.get_single("Volunteering Accounting Settings")
	settings.use_grade_approval = 1
	settings.use_designation_approval = 1
	# Budget override is the Board of Directors grade now.
	settings.budget_override_role = None
	settings.save(ignore_permissions=True)
