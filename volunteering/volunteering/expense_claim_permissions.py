"""Row-level permissions for Expense Claim.

Accounts and board-level employees see everything. Department heads
(`Department.department_head`) see their department's claims.
Everyone else sees their own claims plus claims where they are the
pending / expense approver.

List filtering must not rely on Employee User Permissions: Accounts staff
are also Employees, so an apply-to-all Employee UP would hide every claim
that is not their own (usually none). Row scope lives in these hooks;
``employee`` has ``ignore_user_permissions`` set for that reason.
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

	conditions = []
	own_employee = get_employee_for_user(user)
	if own_employee:
		conditions.append(f"`tabExpense Claim`.employee = {frappe.db.escape(own_employee)}")

	user_esc = frappe.db.escape(user)
	conditions.append(f"`tabExpense Claim`.pending_approver = {user_esc}")
	if frappe.db.has_column("Expense Claim", "expense_approver"):
		conditions.append(f"`tabExpense Claim`.expense_approver = {user_esc}")

	departments = departments_headed_by(user)
	if departments:
		employees = frappe.get_all(
			"Employee",
			filters={"department": ["in", departments], "status": "Active"},
			pluck="name",
		)
		if employees:
			escaped = ", ".join(frappe.db.escape(employee) for employee in employees)
			conditions.append(f"`tabExpense Claim`.employee IN ({escaped})")
	elif DEPT_HEAD_ROLE in roles and not own_employee:
		return "1=0"

	if not conditions:
		return "1=0"

	return "(" + " OR ".join(conditions) + ")"


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if _has_full_access(user, roles):
		return True

	own_employee = get_employee_for_user(user)
	if own_employee and doc.get("employee") == own_employee:
		return True

	if doc.get("pending_approver") == user or doc.get("expense_approver") == user:
		return True

	departments = departments_headed_by(user)
	if departments:
		employee_department = frappe.db.get_value("Employee", doc.employee, "department")
		if employee_department in departments:
			return True

	# Create is gated by DocType roles + validate elsewhere.
	if ptype == "create":
		return True

	return False
