"""Row-level permissions for Employee Advance.

Employees create/see only their own advances.
Managers see reportees (reports_to).
Accounts / HR / System Manager and board-level grades see all.
"""

from __future__ import annotations

import frappe
from frappe import _

from volunteering.volunteering.accounting_dashboard.constants import (
	ACCOUNTS_ROLES,
	BOARD_ROLES,
)
from volunteering.volunteering.authority import user_is_board_level

HR_ROLES = frozenset({"HR Manager", "HR User", "System Manager", "Administrator"})
FULL_ACCESS_ROLES = ACCOUNTS_ROLES | BOARD_ROLES | HR_ROLES


def _has_full_access(user, roles=None):
	roles = roles if roles is not None else set(frappe.get_roles(user))
	return bool(roles.intersection(FULL_ACCESS_ROLES)) or user_is_board_level(user)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if _has_full_access(user, roles):
		return ""

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return "1=0"

	own = frappe.db.escape(employee)
	return f"""(`tabEmployee Advance`.employee = {own}
		OR `tabEmployee Advance`.employee IN (
			SELECT name FROM `tabEmployee` WHERE reports_to = {own}
		))"""


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if _has_full_access(user, roles):
		return True

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return False

	is_own = doc.employee == employee
	is_manager = frappe.db.get_value("Employee", doc.employee, "reports_to") == employee

	if ptype in {"read", "print", "email", "export", "report", "select"}:
		return is_own or is_manager

	# Create / write / delete only for own advances (non-Accounts)
	if ptype in {"write", "create", "delete"}:
		return is_own

	# Submit/cancel: Accounts already returned True; managers may read only
	if ptype in {"submit", "cancel", "amend"}:
		return False

	return False


def validate_employee_self_only(doc, method=None):
	"""Non-Accounts/HR users may only create advances for themselves."""
	if frappe.session.user == "Administrator":
		return

	if _has_full_access(frappe.session.user):
		return

	session_employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user}, "name"
	)
	if not session_employee:
		frappe.throw(_("Your user is not linked to an Employee record."))

	if not doc.employee:
		doc.employee = session_employee
	elif doc.employee != session_employee:
		frappe.throw(_("You can only create Employee Advances for yourself."))
