"""Row-level permissions for Attendance Request (WFH approvals by reporting managers).

Employees create their own requests but cannot submit (approve) them.
The reporting manager (Employee.reports_to) approves by submitting.
HR Manager / HR User / System Manager retain full access.
"""

import frappe
from frappe import _

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
		# #region agent log
		_agent_dbg("A", "attendance_request_permissions.py:has_permission", "no employee for user", {"user": user, "ptype": ptype})
		# #endregion
		return False

	is_own = doc.employee == employee
	is_manager = frappe.db.get_value("Employee", doc.employee, "reports_to") == employee

	# Approval actions: only the reporting manager
	if ptype in {"submit", "cancel", "amend"}:
		# #region agent log
		_agent_dbg(
			"A",
			"attendance_request_permissions.py:has_permission",
			"submit/cancel check",
			{
				"user": user,
				"ptype": ptype,
				"doc_employee": doc.employee,
				"session_employee": employee,
				"is_own": is_own,
				"is_manager": is_manager,
				"allowed": is_manager,
			},
		)
		# #endregion
		return is_manager

	if ptype in {"read", "print", "email", "export", "report"}:
		return is_own or is_manager

	# Draft editing/creation stays with the requesting employee
	if ptype in {"write", "create", "delete"}:
		return is_own

	return False


def validate_attendance_request(doc, method=None):
	"""Non-HR users may only create Attendance Requests for themselves."""
	if frappe.session.user == "Administrator":
		return
	roles = set(frappe.get_roles(frappe.session.user))
	if roles.intersection(HR_ROLES):
		return

	session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not session_employee:
		frappe.throw(_("Your user is not linked to an Employee record."))

	if not doc.employee:
		doc.employee = session_employee
	elif doc.employee != session_employee:
		frappe.throw(_("You can only create Attendance Requests for yourself."))


def _agent_dbg(hypothesis_id, location, message, data):
	try:
		import json
		import time

		with open(
			"/Users/varunkumar/Documents/coding/erp/erpnext/frappe-bench/.cursor/debug-4c4245.log",
			"a",
			encoding="utf-8",
		) as f:
			f.write(
				json.dumps(
					{
						"sessionId": "4c4245",
						"hypothesisId": hypothesis_id,
						"location": location,
						"message": message,
						"data": data,
						"timestamp": int(time.time() * 1000),
						"runId": "pre-fix",
					}
				)
				+ "\n"
			)
	except Exception:
		pass

