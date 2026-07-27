# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Grant volunteering ops (org dashboard) access to selected users.

NGO Member alone = own Volunteer / Participation / Reciprocation only.
NGO Coordinator (or Admin / Department Head) = organisation-wide metrics + records.

Usage (bench console / execute):

  volunteering.volunteering.volunteering_ops_setup.grant_ops_access("user@example.com")
"""

from __future__ import annotations

import frappe

OPS_ROLE = "NGO Coordinator"


def ensure_ops_role_exists():
	if not frappe.db.exists("Role", OPS_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": OPS_ROLE, "desk_access": 1}).insert(ignore_permissions=True)


def grant_ops_access(user: str, commit: bool = True) -> dict:
	"""Add NGO Coordinator so Volunteering workspace cards/charts show org totals."""
	ensure_ops_role_exists()
	if not frappe.db.exists("User", user):
		frappe.throw(f"User {user} not found")

	has = frappe.db.exists("Has Role", {"parent": user, "role": OPS_ROLE})
	if not has:
		doc = frappe.get_doc("User", user)
		doc.append("roles", {"role": OPS_ROLE})
		doc.save(ignore_permissions=True)
		if commit:
			frappe.db.commit()

	return {
		"user": user,
		"role": OPS_ROLE,
		"added": not bool(has),
		"roles": frappe.get_roles(user),
	}


def revoke_ops_access(user: str, commit: bool = True) -> dict:
	"""Remove NGO Coordinator (does not remove NGO Member)."""
	if frappe.db.exists("Has Role", {"parent": user, "role": OPS_ROLE}):
		frappe.db.delete("Has Role", {"parent": user, "role": OPS_ROLE})
		if commit:
			frappe.db.commit()
	frappe.clear_cache(user=user)
	return {"user": user, "role": OPS_ROLE, "removed": True}
