# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Restrict Attendance list/form to self + reportees (employees)."""

import frappe

import frappe

HR_ROLES = {"HR Manager", "HR User", "System Manager"}
# Only HR sees all attendance rows. Employee (+ other ops roles) limited to self + reportees.
FULL_ACCESS_ROLES = HR_ROLES



def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	# #region agent log
	_agent_dbg(
		"C",
		"attendance_permissions.py:get_permission_query_conditions",
		"attendance list query",
		{"user": user, "roles": frappe.get_roles(user)},
	)
	# #endregion

	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if roles.intersection(FULL_ACCESS_ROLES):
		# #region agent log
		_agent_dbg(
			"C",
			"attendance_permissions.py:get_permission_query_conditions",
			"full access role — no filter",
			{"roles": list(roles.intersection(FULL_ACCESS_ROLES))},
		)
		# #endregion
		return ""

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return "1=0"

	own = frappe.db.escape(employee)
	condition = (
		f"(`tabAttendance`.employee = {own} "
		f"OR `tabAttendance`.employee IN ("
		f"SELECT name FROM `tabEmployee` WHERE reports_to = {own}))"
	)
	# #region agent log
	_agent_dbg(
		"C",
		"attendance_permissions.py:get_permission_query_conditions",
		"filter self+reportees applied",
		{"employee": employee, "filter_applied": True},
	)
	# #endregion
	return condition


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles.intersection(FULL_ACCESS_ROLES):
		return True

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return False

	is_own = doc.employee == employee
	is_manager = frappe.db.get_value("Employee", doc.employee, "reports_to") == employee
	allowed = is_own or is_manager

	# #region agent log
	if ptype in ("read", "write"):
		_agent_dbg(
			"C",
			"attendance_permissions.py:has_permission",
			"attendance doc access",
			{
				"user": user,
				"ptype": ptype,
				"doc_employee": getattr(doc, "employee", None),
				"is_own": is_own,
				"is_manager": is_manager,
				"allowed": allowed,
			},
		)
	# #endregion

	return allowed


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
						"runId": "post-fix",
					}
				)
				+ "\n"
			)
	except Exception:
		pass
