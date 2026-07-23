# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Volunteer DocType permissions (Volunteer has email, not user_id)."""

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

	# #region agent log
	agent_dbg(
		"H1",
		"volunteer_permissions.py:get_permission_query_conditions",
		"volunteer query entry",
		{"user": user, "ops": user_has_volunteering_ops_access(user)},
	)
	# #endregion

	if user_has_volunteering_ops_access(user):
		return ""

	roles = set(frappe.get_roles(user))
	if "NGO Member" in roles:
		email = volunteer_email_for_user(user)
		return f"`tabVolunteer`.email = {frappe.db.escape(email)}"

	return "1=0"


def has_permission(doc, ptype="read", user=None):
	user = user or frappe.session.user
	if user_has_volunteering_ops_access(user):
		return True
	if "NGO Member" in frappe.get_roles(user):
		return (doc.get("email") or "").lower() == (volunteer_email_for_user(user) or "").lower()
	return False
