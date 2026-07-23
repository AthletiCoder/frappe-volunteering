# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Participation DocType permissions — Volunteer is matched by email (no user_id)."""

from __future__ import annotations

import frappe

from volunteering.volunteering.volunteering_access import (
	agent_dbg,
	user_has_volunteering_ops_access,
	volunteer_email_for_user,
)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	ops = user_has_volunteering_ops_access(user)
	# #region agent log
	agent_dbg(
		"H2",
		"participation_permissions.py:get_permission_query_conditions",
		"participation query entry",
		{"user": user, "ops": ops, "roles_has_member": "NGO Member" in frappe.get_roles(user)},
	)
	# #endregion

	if ops:
		return ""

	if "NGO Member" in frappe.get_roles(user):
		email = volunteer_email_for_user(user)
		cond = (
			"`tabParticipation`.volunteer in ("
			f"select name from `tabVolunteer` where email = {frappe.db.escape(email)}"
			")"
		)
		# #region agent log
		agent_dbg("H2", "participation_permissions.py:member_filter", "self filter", {"email": email})
		# #endregion
		return cond

	return "1=0"


def has_permission(doc, ptype="read", user=None):
	user = user or frappe.session.user
	if user_has_volunteering_ops_access(user):
		return True
	if "NGO Member" in frappe.get_roles(user):
		email = volunteer_email_for_user(user)
		vol_email = frappe.db.get_value("Volunteer", doc.get("volunteer"), "email")
		return (vol_email or "").lower() == (email or "").lower()
	return False
