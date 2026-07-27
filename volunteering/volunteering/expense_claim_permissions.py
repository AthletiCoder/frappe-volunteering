import frappe

from volunteering.volunteering.accounting_dashboard.constants import (
	ACCOUNTS_ROLES,
	BOARD_ROLES,
	DEPT_HEAD_ROLE,
)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if roles.intersection(ACCOUNTS_ROLES) or roles.intersection(BOARD_ROLES):
		return ""

	if DEPT_HEAD_ROLE not in roles:
		return ""

	departments = frappe.get_all(
		"Department",
		filters={"department_head": user},
		pluck="name",
	)
	if not departments:
		return "1=0"

	employees = frappe.get_all(
		"Employee",
		filters={"department": ["in", departments], "status": "Active"},
		pluck="name",
	)
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
	if roles.intersection(ACCOUNTS_ROLES) or roles.intersection(BOARD_ROLES):
		return True

	if DEPT_HEAD_ROLE not in roles:
		return True

	if ptype not in ("read", "print", "email", "export", "select"):
		return True

	departments = frappe.get_all(
		"Department",
		filters={"department_head": user},
		pluck="name",
	)
	if not departments:
		return False

	employee_department = frappe.db.get_value("Employee", doc.employee, "department")
	return employee_department in departments
