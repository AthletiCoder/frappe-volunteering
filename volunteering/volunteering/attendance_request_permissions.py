"""Row-level permissions for Attendance Request (WFH approvals by reporting managers).

Employees create their own requests but cannot submit (approve) them.
The reporting manager (Employee.reports_to) approves by submitting.
HR Manager / HR User / System Manager retain full access.
"""

import frappe

HR_ROLES = {"HR Manager", "HR User", "System Manager"}


def ensure_attendance_request_permissions():
	"""Grant Employee role submit rights via Custom DocPerm (upgrade-safe, no HRMS changes)."""
	from frappe.permissions import update_permission_property

	update_permission_property("Attendance Request", "Employee", 0, "submit", 1, validate=False)
	frappe.clear_cache(doctype="Attendance Request")


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if roles.intersection(HR_ROLES):
		return ""

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return "1=0"

	own = frappe.db.escape(employee)
	return f"""(`tabAttendance Request`.employee = {own}
		OR `tabAttendance Request`.employee IN (
			SELECT name FROM `tabEmployee` WHERE reports_to = {own}
		))"""


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles.intersection(HR_ROLES):
		return True

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return False

	is_own = doc.employee == employee
	is_manager = frappe.db.get_value("Employee", doc.employee, "reports_to") == employee

	# Approval actions: only the reporting manager
	if ptype in {"submit", "cancel", "amend"}:
		return is_manager

	if ptype in {"read", "print", "email", "export", "report"}:
		return is_own or is_manager

	# Draft editing/creation stays with the requesting employee
	if ptype in {"write", "create", "delete"}:
		return is_own

	return False
