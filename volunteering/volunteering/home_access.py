# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Pure role → Home section flags. No DocType queries here (unit-testable)."""

from __future__ import annotations

from volunteering.volunteering.accounting_dashboard.constants import ACCOUNTS_ROLES
from volunteering.volunteering.accounting_setup import BUDGET_HEALTH_ROLES
from volunteering.volunteering.authority import BOARD_OF_DIRECTORS
from volunteering.volunteering.volunteering_access import VOLUNTEERING_OPS_ROLES

HR_ROLES = frozenset({"HR Manager", "HR User"})
APPROVER_ROLES = frozenset({"Leave Approver", "Expense Approver"})
STAFF_HOME_ROLES = frozenset(
	{
		"Employee",
		"Accounts User",
		"Accounts Manager",
		"System Manager",
		"HR Manager",
		"HR User",
		"NGO Coordinator",
		"NGO Admin",
		"Leave Approver",
		"Expense Approver",
	}
)


def classify_home_access(roles, has_employee, grade=None):
	"""Return section flags for Home. `roles` is an iterable of role names."""
	role_set = set(roles or ())
	grade = grade or ""
	is_admin_user = "System Manager" in role_set or "Administrator" in role_set
	is_accounts = bool(role_set & ACCOUNTS_ROLES) or is_admin_user
	is_hr = bool(role_set & HR_ROLES)
	is_ops = bool(role_set & VOLUNTEERING_OPS_ROLES)
	is_board = grade == BOARD_OF_DIRECTORS
	has_staff_role = bool(role_set & STAFF_HOME_ROLES) or is_admin_user or is_board
	volunteer_only = "NGO Member" in role_set and not has_employee and not has_staff_role

	allowed = (has_staff_role or has_employee) and not volunteer_only
	if is_admin_user:
		allowed = True

	show_time = allowed and (has_employee or is_admin_user)
	show_money = show_time
	show_approver_inbox = allowed and (
		bool(role_set & APPROVER_ROLES) or is_admin_user or is_board
	)
	show_accounts = allowed and is_accounts
	show_programs = allowed and is_ops
	show_people = allowed and (is_hr or is_admin_user)
	show_admin = allowed and (is_admin_user or is_board)
	show_budget_health = allowed and (
		bool(role_set.intersection(BUDGET_HEALTH_ROLES)) or is_admin_user or is_board
	)
	show_advances = allowed and (has_employee or is_accounts)

	persona = _persona(
		allowed=allowed,
		is_admin_user=is_admin_user,
		is_board=is_board,
		is_accounts=is_accounts,
		is_hr=is_hr,
		is_ops=is_ops,
		show_approver_inbox=show_approver_inbox,
		has_employee=has_employee,
	)

	return {
		"allowed": allowed,
		"persona": persona,
		"show_time": show_time,
		"show_money": show_money,
		"show_approver_inbox": show_approver_inbox,
		"show_accounts": show_accounts,
		"show_programs": show_programs,
		"show_people": show_people,
		"show_admin": show_admin,
		"show_budget_health": show_budget_health,
		"show_advances": show_advances,
		"deemphasize_self_service": show_accounts or show_people or show_programs,
	}


def _persona(
	allowed,
	is_admin_user,
	is_board,
	is_accounts,
	is_hr,
	is_ops,
	show_approver_inbox,
	has_employee,
):
	if not allowed:
		return "volunteer"
	if is_admin_user or is_board:
		return "admin"
	if is_accounts:
		return "accounts"
	if is_hr:
		return "hr"
	if is_ops:
		return "coordinator"
	if show_approver_inbox:
		return "manager"
	if has_employee:
		return "employee"
	return "employee"
