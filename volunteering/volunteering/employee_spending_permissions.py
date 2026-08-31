"""DocPerm grants so employees can use expense / advance forms without manual Role Permission Manager."""

import frappe
from frappe.permissions import add_permission, update_permission_property

EMPLOYEE_SELF_SERVICE_DOCTYPES = (
	"Project",
	"Currency",
	"Cost Center",
	"Expense Claim Type",
)


def ensure_employee_self_service_permissions():
	"""Employee role: read/select masters needed for EC, EA, and project tagging."""
	if not frappe.db.exists("Role", "Employee"):
		return

	for doctype in EMPLOYEE_SELF_SERVICE_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists(
			"Custom DocPerm",
			{"parent": doctype, "role": "Employee", "permlevel": 0, "if_owner": 0},
		):
			add_permission(doctype, "Employee", permlevel=0, ptype="read")
		for perm in ("read", "select"):
			update_permission_property(doctype, "Employee", 0, perm, 1, validate=False)
		frappe.clear_cache(doctype=doctype)
