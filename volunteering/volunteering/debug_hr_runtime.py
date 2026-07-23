# Copyright (c) 2026 - temporary debug probe
from __future__ import annotations

import json
import time

import frappe

LOG = "/Users/varunkumar/Documents/coding/erp/erpnext/frappe-bench/.cursor/debug-4c4245.log"


def _log(hid, message, data):
	with open(LOG, "a", encoding="utf-8") as f:
		f.write(
			json.dumps(
				{
					"sessionId": "4c4245",
					"hypothesisId": hid,
					"location": "debug_hr_runtime.probe_pending_leave",
					"message": message,
					"data": data,
					"timestamp": int(time.time() * 1000),
					"runId": "pending-leave",
				},
				default=str,
			)
			+ "\n"
		)


def probe_pending_leave():
	opens = frappe.get_all(
		"Leave Application",
		filters={"status": "Open", "docstatus": 0},
		fields=["name", "employee", "leave_approver", "status", "owner"],
	)
	for row in opens:
		emp = frappe.db.get_value(
			"Employee",
			row.employee,
			["name", "employee_name", "user_id", "leave_approver", "reports_to"],
			as_dict=True,
		)
		mgr_user = (
			frappe.db.get_value("Employee", emp.reports_to, "user_id")
			if emp and emp.reports_to
			else None
		)
		_log(
			"H1",
			"open leave mapping",
			{
				"leave": row.name,
				"employee": emp.name if emp else None,
				"emp_user": emp.user_id if emp else None,
				"emp_leave_approver": emp.leave_approver if emp else None,
				"app_leave_approver": row.leave_approver,
				"reports_to": emp.reports_to if emp else None,
				"reports_to_user": mgr_user,
				"approver_matches_reports_to_user": row.leave_approver == mgr_user,
			},
		)

	emps = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name", "user_id", "reports_to", "leave_approver"],
	)
	for e in emps:
		reportees = [x for x in emps if x.reports_to == e.name]
		if reportees:
			_log(
				"H2",
				"manager with reportees",
				{
					"manager_emp": e.name,
					"manager_user": e.user_id,
					"reportees": [
						{
							"emp": r.name,
							"user": r.user_id,
							"leave_approver": r.leave_approver,
						}
						for r in reportees
					],
				},
			)

	results = {}
	for user in ["Administrator", "nived@sevamrita.org"]:
		frappe.set_user(user)
		by_approver = frappe.get_all(
			"Leave Application",
			filters={"leave_approver": user, "status": "Open", "docstatus": 0},
			pluck="name",
		)
		my_emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
		reportee_emps = (
			frappe.get_all("Employee", filters={"reports_to": my_emp}, pluck="name")
			if my_emp
			else []
		)
		by_reports = (
			frappe.get_all(
				"Leave Application",
				filters={
					"employee": ["in", reportee_emps],
					"status": "Open",
					"docstatus": 0,
				},
				pluck="name",
			)
			if reportee_emps
			else []
		)
		# get_list applies permissions
		listed = frappe.get_list(
			"Leave Application",
			filters={"status": "Open", "docstatus": 0},
			fields=["name", "leave_approver", "employee"],
			limit_page_length=50,
		)
		payload = {
			"user": user,
			"my_emp": my_emp,
			"by_leave_approver": by_approver,
			"reportee_emps": reportee_emps,
			"by_reports_to": by_reports,
			"get_list_open": listed,
			"can_read": frappe.has_permission("Leave Application", "read"),
			"roles": [
				r
				for r in frappe.get_roles(user)
				if r
				in (
					"Leave Approver",
					"HR Manager",
					"HR User",
					"Employee",
					"System Manager",
				)
			],
		}
		_log("H3", "pending visibility", payload)
		results[user] = payload

	return {"opens": opens, "results": results}
