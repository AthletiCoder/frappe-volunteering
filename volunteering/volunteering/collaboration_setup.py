"""Idempotent chat roles and migration. Web chat always requires an explicit grant."""
import frappe
from volunteering.volunteering.collaboration_access import APP_ROLE, WEB_ROLE, LEGACY_ROLE


def ensure_chat_role():
	for role in (WEB_ROLE, APP_ROLE):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0}).insert(ignore_permissions=True)
		elif frappe.db.get_value("Role", role, "desk_access"):
			# Frappe may create roles referenced by a new DocType with Desk
			# enabled before after_migrate runs. These are portal/app roles.
			frappe.db.set_value("Role", role, "desk_access", 0, update_modified=False)
	# Preserve existing chat participation in the app. Do not enroll anybody in
	# the web collaboration UI, which changes their normal ERP Home experience.
	legacy = frappe.get_all("Has Role", filters={"parenttype": ["in", ["User", "Role Profile"]], "role": LEGACY_ROLE},
		fields=["name", "parent", "parenttype"])
	for row in legacy:
		if frappe.db.exists("Has Role", {"parent": row.parent, "parenttype": row.parenttype, "role": APP_ROLE}):
			frappe.db.delete("Has Role", row.name)
		else:
			frappe.db.set_value("Has Role", row.name, "role", APP_ROLE, update_modified=False)
		if row.parenttype == "User":
			frappe.clear_cache(user=row.parent)
	# Retire the previous combined role after migrating users and role profiles.
	if frappe.db.exists("Role", LEGACY_ROLE) and frappe.get_meta("Role").has_field("disabled"):
		frappe.db.set_value("Role", LEGACY_ROLE, "disabled", 1, update_modified=False)
	for doctype, fields in [("Space", ["root_space", "archived"]), ("Member", ["user", "parent"]),
		("Entry", ["space", "creation"]), ("Item", ["space", "item_kind", "status"]), ("Read State", ["user", "space"])]:
		if frappe.db.table_exists("Collaboration " + doctype):
			frappe.db.add_index("Collaboration " + doctype, fields)
