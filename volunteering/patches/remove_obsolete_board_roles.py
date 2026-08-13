"""Delete the Board / Department Head roles now that authority is Grade based.

Run after `migrate_authority_to_grade` has copied authority onto
Employee.grade and Department.department_head.
"""

from __future__ import annotations

import frappe

from volunteering.volunteering.authority import LEGACY_BOARD_ROLES, LEGACY_ROLE_DEPT_HEAD

OBSOLETE_ROLES = sorted(LEGACY_BOARD_ROLES | {LEGACY_ROLE_DEPT_HEAD})

# Role names are stored as values in these (doctype, fieldname) pairs.
ROLE_REFERENCE_TABLES = (
	("Has Role", "role"),
	("DocPerm", "role"),
	("Custom DocPerm", "role"),
	("Workspace Role", "role"),
	("Workflow Document State", "allow_edit"),
	("Workflow Transition", "allowed"),
	("Notification Recipient", "role"),
	("Desk Icon Role", "role"),
)


def execute():
	for role in OBSOLETE_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		_drop_role_references(role)
		frappe.delete_doc("Role", role, ignore_permissions=True, force=True)

	frappe.clear_cache()


def _drop_role_references(role):
	for doctype, fieldname in ROLE_REFERENCE_TABLES:
		if not frappe.db.table_exists(f"tab{doctype}"):
			continue
		frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE `{fieldname}` = %s", (role,))

	if frappe.db.exists("DocType", "Volunteering Accounting Settings"):
		if frappe.db.get_single_value("Volunteering Accounting Settings", "budget_override_role") == role:
			frappe.db.set_single_value("Volunteering Accounting Settings", "budget_override_role", None)

	_strip_from_digest_roles(role)


def _strip_from_digest_roles(role):
	if not frappe.db.exists("DocType", "Daily Work Log Settings"):
		return

	raw = frappe.db.get_single_value("Daily Work Log Settings", "digest_recipient_roles")
	if not raw or role not in raw:
		return

	remaining = [
		line.strip()
		for line in raw.replace(",", "\n").split("\n")
		if line.strip() and line.strip() != role
	]
	frappe.db.set_single_value(
		"Daily Work Log Settings", "digest_recipient_roles", "\n".join(remaining)
	)
