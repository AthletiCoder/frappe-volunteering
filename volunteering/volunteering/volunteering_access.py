# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Shared volunteering data-access roles.

- Ops / dashboard roles see all Volunteer, Participation, Reciprocation (org metrics).
- NGO Member alone sees only their own Volunteer-linked rows (portal self-service).
- Everyone else is denied (1=0).

Assign **NGO Coordinator** (or NGO Admin) to staff who should see the Volunteering
workspace cards/charts with correct organisation-wide numbers.
"""

from __future__ import annotations

import frappe

# Full org visibility for volunteering masters / transactions
VOLUNTEERING_OPS_ROLES = frozenset(
	{
		"NGO Admin",
		"NGO Coordinator",
		"NGO Department Head",
		"System Manager",
		"Administrator",
	}
)

# Legacy alias used by permission modules
FULL_ACCESS_ROLES = VOLUNTEERING_OPS_ROLES


def has_app_permission() -> bool:
	"""Show the Volunteering app to users assigned any NGO-prefixed role."""
	return any(role.startswith("NGO ") for role in frappe.get_roles())


def user_has_volunteering_ops_access(user=None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)).intersection(VOLUNTEERING_OPS_ROLES))


def volunteer_email_for_user(user) -> str:
	"""Volunteer is matched to User by email (Volunteer has no user_id field)."""
	email = frappe.db.get_value("User", user, "email")
	return email or user
