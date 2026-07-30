# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Reciprocation DocType permissions — Volunteer is matched by email (no user_id)."""

from __future__ import annotations

import frappe

from volunteering.volunteering.volunteering_access import (
	user_has_volunteering_ops_access,
	volunteer_email_for_user,
)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user_has_volunteering_ops_access(user):
		return ""

	if "NGO Member" in frappe.get_roles(user):
		email = volunteer_email_for_user(user)
		# Volunteer has `email`, not `user_id` — previous SQL caused Error 1054
		return (
			"`tabReciprocation`.volunteer in ("
			f"select name from `tabVolunteer` where email = {frappe.db.escape(email)}"
			")"
		)

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
