"""Row-level permissions for Expense Claim.

Accounts and board-level employees see everything. Department heads
(`Department.department_head`) see their department's claims.
"""

import frappe

from volunteering.volunteering.accounting_dashboard.constants import (
	ACCOUNTS_ROLES,
	DEPT_HEAD_ROLE,
)
from volunteering.volunteering.authority import (
	departments_headed_by,
	get_employee_for_user,
	user_is_board_level,
)


def _has_full_access(user, roles):
	return bool(roles.intersection(ACCOUNTS_ROLES)) or user_is_board_level(user)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if _has_full_access(user, roles):
		return ""

	departments = departments_headed_by(user)
	if not departments:
		# Legacy role holders without a department master stay locked down.
		return "1=0" if DEPT_HEAD_ROLE in roles else ""

	employees = frappe.get_all(
		"Employee",
		filters={"department": ["in", departments], "status": "Active"},
		pluck="name",
	)
	own_employee = get_employee_for_user(user)
	if own_employee and own_employee not in employees:
		employees.append(own_employee)
	if not employees:
		return "1=0"

	escaped = ", ".join(frappe.db.escape(employee) for employee in employees)
	return f"`tabExpense Claim`.employee IN ({escaped})"


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if _has_full_access(user, roles):
		return True

	if ptype not in ("read", "print", "email", "export", "select"):
		return True

	departments = departments_headed_by(user)
	if not departments:
		return DEPT_HEAD_ROLE not in roles

	if doc.employee and doc.employee == get_employee_for_user(user):
		return True

	employee_department = frappe.db.get_value("Employee", doc.employee, "department")
	return employee_department in departments
