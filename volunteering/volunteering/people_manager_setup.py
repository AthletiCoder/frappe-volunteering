# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""People Manager role — auto-granted to anyone with reportees (reports_to)."""

from __future__ import annotations

import frappe

PEOPLE_MANAGER_ROLE = "People Manager"


def ensure_people_manager_role():
	if frappe.db.exists("Role", PEOPLE_MANAGER_ROLE):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": PEOPLE_MANAGER_ROLE,
			"desk_access": 1,
			"description": "Has direct reportees; sees Awaiting my Approval queues.",
		}
	).insert(ignore_permissions=True)


def sync_people_manager_role(doc=None, method=None):
	"""On Employee validate: grant/revoke People Manager based on reportees."""
	ensure_people_manager_role()
	# After this employee is saved, refresh the manager they report to and themselves
	targets = set()
	if doc:
		if doc.name:
			targets.add(doc.name)
		if doc.reports_to:
			targets.add(doc.reports_to)
	for emp in targets:
		_sync_employee_people_manager(emp)


def backfill_people_manager_roles():
	"""after_migrate: grant People Manager to every user who has at least one reportee."""
	ensure_people_manager_role()
	managers = frappe.db.sql(
		"""
		SELECT DISTINCT reports_to
		FROM `tabEmployee`
		WHERE reports_to IS NOT NULL AND reports_to != '' AND status = 'Active'
		""",
		pluck=True,
	)
	granted = 0
	for emp in managers:
		if _sync_employee_people_manager(emp):
			granted += 1

	# Revoke from users who no longer have reportees
	users_with_role = frappe.get_all(
		"Has Role",
		filters={"role": PEOPLE_MANAGER_ROLE, "parenttype": "User"},
		pluck="parent",
	)
	for user in users_with_role:
		emp = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
		if not emp:
			_revoke_role(user)
			continue
		has_reportees = frappe.db.exists(
			"Employee", {"reports_to": emp, "status": "Active"}
		)
		if not has_reportees:
			_revoke_role(user)

	return {"managers": len(managers), "granted": granted}


def _sync_employee_people_manager(employee_name: str) -> bool:
	user = frappe.db.get_value("Employee", employee_name, "user_id")
	if not user or user in ("Guest", "Administrator"):
		return False

	has_reportees = bool(
		frappe.db.exists("Employee", {"reports_to": employee_name, "status": "Active"})
	)
	has_role = frappe.db.exists("Has Role", {"parent": user, "role": PEOPLE_MANAGER_ROLE})

	if has_reportees and not has_role:
		user_doc = frappe.get_doc("User", user)
		user_doc.append("roles", {"role": PEOPLE_MANAGER_ROLE})
		user_doc.save(ignore_permissions=True)
		# Also ensure Leave Approver for leave queues
		if not frappe.db.exists("Has Role", {"parent": user, "role": "Leave Approver"}):
			user_doc = frappe.get_doc("User", user)
			user_doc.append("roles", {"role": "Leave Approver"})
			user_doc.save(ignore_permissions=True)
		return True

	if not has_reportees and has_role:
		_revoke_role(user)
	return False


def _revoke_role(user: str):
	frappe.db.delete("Has Role", {"parent": user, "role": PEOPLE_MANAGER_ROLE})
	frappe.clear_cache(user=user)
