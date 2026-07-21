import frappe


ROLE_MAP = {
	"NGO Board Member": "Executive Board Member",
	"NGO Board Chairperson": "Executive Board Chairperson",
}

REFERENCE_TABLES = (
	("Has Role", "role"),
	("DocPerm", "role"),
	("Custom DocPerm", "role"),
	("Workflow Document State", "allow_edit"),
	("Workflow Transition", "allowed"),
	("Notification Recipient", "role"),
	("Report Filter", None),
)


def execute():
	for old_name, new_name in ROLE_MAP.items():
		_rename_role(old_name, new_name)


def _rename_role(old_name, new_name):
	if frappe.db.exists("Role", new_name):
		if frappe.db.exists("Role", old_name):
			_repoint_role_references(old_name, new_name)
			frappe.delete_doc("Role", old_name, force=True, ignore_permissions=True)
		return

	if not frappe.db.exists("Role", old_name):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": new_name,
				"desk_access": 1,
			}
		).insert(ignore_permissions=True)
		return

	try:
		frappe.rename_doc("Role", old_name, new_name, force=True, merge=False)
	except Exception:
		frappe.db.set_value("Role", old_name, {"name": new_name, "role_name": new_name})
		_repoint_role_references(old_name, new_name)


def _repoint_role_references(old_name, new_name):
	# Has Role / DocPerm are the main places Role names are stored as values.
	for doctype, field in (
		("Has Role", "role"),
		("DocPerm", "role"),
		("Custom DocPerm", "role"),
	):
		if not frappe.db.exists("DocType", doctype):
			continue
		frappe.db.sql(
			f"UPDATE `tab{doctype}` SET `{field}` = %s WHERE `{field}` = %s",
			(new_name, old_name),
		)

	# Workspace roles (if present)
	if frappe.db.exists("DocType", "Workspace"):
		workspaces = frappe.get_all("Workspace", fields=["name", "roles"])
		# roles is a child table Workspace Role
		if frappe.db.exists("DocType", "Has Role"):
			pass
		if frappe.db.table_exists("tabWorkspace Role"):
			frappe.db.sql(
				"UPDATE `tabWorkspace Role` SET role = %s WHERE role = %s",
				(new_name, old_name),
			)
