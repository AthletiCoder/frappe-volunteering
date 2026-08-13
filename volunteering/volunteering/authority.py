# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Authority helpers: who may approve, who is board level, who heads a department.

Authority lives on Employee records, not on User Roles:

- **Grade** (`Employee.grade`) is the seniority band. Amount limits per grade are
  configured on **Approval and Advance Limits**.
- **Department head** (`Department.department_head`) grants department-scoped
  visibility.

The legacy Board / Department Head *roles* are still honoured (dual path) so
sites keep working between `migrate_authority_to_grade` and
`remove_obsolete_board_roles`. Once the second patch runs, only grades and
department heads matter.
"""

from __future__ import annotations

import frappe

BOARD_OF_DIRECTORS = "Board of Directors"
EXECUTIVE_BOARD = "Executive Board"
BOARD_GRADES = frozenset({BOARD_OF_DIRECTORS, EXECUTIVE_BOARD})

# --- Legacy roles: dual path until remove_obsolete_board_roles runs ---------
LEGACY_ROLE_BOARD_CHAIR = "NGO Board Chairperson"
LEGACY_ROLE_BOARD_MEMBER = "NGO Board Member"
LEGACY_ROLE_EXEC_CHAIR = "Executive Board Chairperson"
LEGACY_ROLE_EXEC_BOARD = "Executive Board Member"
LEGACY_ROLE_DEPT_HEAD = "NGO Department Head"

LEGACY_CHAIR_ROLES = frozenset({LEGACY_ROLE_BOARD_CHAIR, LEGACY_ROLE_EXEC_CHAIR})
LEGACY_BOARD_MEMBER_ROLES = frozenset({LEGACY_ROLE_BOARD_MEMBER, LEGACY_ROLE_EXEC_BOARD})
LEGACY_BOARD_ROLES = LEGACY_CHAIR_ROLES | LEGACY_BOARD_MEMBER_ROLES

# Workflow transition conditions run in frappe.safe_eval, which only exposes
# frappe.db.get_value / get_list and frappe.session — no imports, no get_attr.
# Keep fixtures/workflow.json in sync with this string.
BOARD_OVERRIDE_WORKFLOW_CONDITION = (
	"frappe.session.user != 'Guest' and ("
	"frappe.db.get_value('Employee', {'user_id': frappe.session.user}, 'grade')"
	" == 'Board of Directors'"
	" or frappe.db.get_value('Has Role', {'parenttype': 'User',"
	" 'parent': frappe.session.user, 'role': 'Executive Board Chairperson'}, 'name')"
	")"
)


def _roles(user) -> set:
	if not user or user == "Guest":
		return set()
	return set(frappe.get_roles(user))


def get_employee_for_user(user):
	"""Employee name linked to a User (None for volunteers / system users)."""
	if not user or user == "Guest":
		return None
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def get_grade_for_employee(employee):
	if not employee:
		return None
	return frappe.db.get_value("Employee", employee, "grade")


def get_grade_for_user(user):
	return get_grade_for_employee(get_employee_for_user(user))


def user_has_board_of_directors(user=None) -> bool:
	"""Top authority: unlimited approval, budget override, create-block."""
	user = user or frappe.session.user
	if get_grade_for_user(user) == BOARD_OF_DIRECTORS:
		return True
	return bool(_roles(user) & LEGACY_CHAIR_ROLES)


def user_has_executive_board(user=None) -> bool:
	user = user or frappe.session.user
	if get_grade_for_user(user) in BOARD_GRADES:
		return True
	return bool(_roles(user) & LEGACY_BOARD_ROLES)


def user_is_board_level(user=None) -> bool:
	user = user or frappe.session.user
	return user_has_executive_board(user) or user_has_board_of_directors(user)


def is_department_head_user(user=None) -> bool:
	user = user or frappe.session.user
	if not user or user == "Guest":
		return False
	if frappe.db.exists(
		"Department", {"department_head": user, "name": ["!=", "All Departments"]}
	):
		return True
	return LEGACY_ROLE_DEPT_HEAD in _roles(user)


def departments_headed_by(user) -> list[str]:
	if not user or user == "Guest":
		return []
	return frappe.get_all("Department", filters={"department_head": user}, pluck="name")


def employees_with_grades(grades) -> list[str]:
	"""user_ids of active employees holding any of the given grades."""
	grades = [grade for grade in (grades or []) if grade]
	if not grades or not frappe.db.has_column("Employee", "grade"):
		return []

	users = []
	for user_id in frappe.get_all(
		"Employee",
		filters={"grade": ["in", grades], "status": "Active", "user_id": ["is", "set"]},
		pluck="user_id",
		order_by="modified asc",
	):
		if user_id and user_id not in users and user_id != "Guest":
			users.append(user_id)
	return users


def get_fallback_board_approver():
	"""Last-resort approver when the reports_to chain runs out."""
	for grade in (BOARD_OF_DIRECTORS, EXECUTIVE_BOARD):
		for user in employees_with_grades([grade]):
			if frappe.db.get_value("User", user, "enabled"):
				return user

	for role in (
		LEGACY_ROLE_BOARD_CHAIR,
		LEGACY_ROLE_EXEC_CHAIR,
		LEGACY_ROLE_BOARD_MEMBER,
		LEGACY_ROLE_EXEC_BOARD,
	):
		for user in frappe.get_all(
			"Has Role",
			filters={"role": role, "parenttype": "User", "parent": ["!=", "Guest"]},
			pluck="parent",
		):
			if frappe.db.get_value("User", user, "enabled"):
				return user
	return None


def session_user_has_board_of_directors() -> bool:
	return user_has_board_of_directors(frappe.session.user)


def session_user_is_board_level() -> bool:
	return user_is_board_level(frappe.session.user)


@frappe.whitelist()
def user_is_board_level_for_session() -> bool:
	"""Client-side gate (Employee Advance form unlocks the employee field)."""
	return bool(session_user_is_board_level())
