"""Privacy-scoped Home dashboard for reporting managers."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, nowdate

from volunteering.volunteering.advance_freeze import (
	direct_reports,
	employee_for_user,
	freeze_status,
)
from volunteering.volunteering.employee_advance_controls import advance_residual_amount


@frappe.whitelist(methods=["POST"])
def get_team_dashboard():
	manager = employee_for_user()
	reports = direct_reports(manager)
	if not reports:
		frappe.throw(_("You do not currently have any active direct reports."), frappe.PermissionError)
	return {
		"manager_employee": manager,
		"as_of": nowdate(),
		"team": [_employee_summary(row) for row in reports],
	}


def _employee_summary(employee):
	return {
		"employee": employee.name,
		"employee_name": employee.employee_name or employee.name,
		"designation": employee.designation,
		"department": employee.department,
		"grade": employee.grade,
		"status": employee.status,
		"date_of_joining": str(employee.date_of_joining) if employee.date_of_joining else "",
		"attendance": _attendance_summary(employee.name),
		"requests": _people_request_summary(employee.name),
		"advances": _advance_summary(employee.name),
		"projects": _project_summary(employee.user_id),
		"advance_control": freeze_status(employee.name),
	}


def _attendance_summary(employee):
	today = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": nowdate(), "docstatus": ["!=", 2]},
		["status", "in_time", "out_time", "working_hours"],
		as_dict=True,
	)
	month_statuses = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": ["between", [get_first_day(nowdate()), nowdate()]],
			"docstatus": ["!=", 2],
		},
		pluck="status",
	)
	month_counts = {}
	for status in month_statuses:
		label = status or "Not marked"
		month_counts[label] = month_counts.get(label, 0) + 1
	return {
		"today": {
			"status": today.status if today else "Not marked",
			"in_time": str(today.in_time) if today and today.in_time else "",
			"out_time": str(today.out_time) if today and today.out_time else "",
			"working_hours": flt(today.working_hours, 2) if today else 0,
		},
		"month": month_counts,
	}


def _people_request_summary(employee):
	return {
		"leave_pending": _count_if_exists(
			"Leave Application", {"employee": employee, "status": "Open", "docstatus": 0}
		),
		"wfh_pending": _count_if_exists("Attendance Request", {"employee": employee, "docstatus": 0}),
		"attendance_fixes_pending": _count_if_exists(
			"Attendance Regularization Request", {"employee": employee, "docstatus": 0}
		),
	}


def _advance_summary(employee):
	rows = frappe.get_all(
		"Employee Advance",
		filters={"employee": employee, "docstatus": ["!=", 2]},
		fields=[
			"name",
			"purpose",
			"status",
			"workflow_state",
			"advance_amount",
			"paid_amount",
			"claimed_amount",
			"return_amount",
			"posting_date",
			"required_by_date",
			"intended_project",
		],
		order_by="posting_date desc, creation desc",
		limit=8,
	)
	return [
		{
			**row,
			"residual": flt(advance_residual_amount(row)),
			"route": f"/desk/employee-advance/{row.name}",
		}
		for row in rows
	]


def _project_summary(user):
	if not user:
		return []
	participant_names = frappe.get_all(
		"Project Participant",
		filters={"user": user, "parenttype": "Project", "parentfield": "project_participants"},
		pluck="parent",
	)
	owned = frappe.get_all("Project", filters={"project_owner": user}, pluck="name")
	names = list(dict.fromkeys([*owned, *participant_names]))
	if not names:
		return []
	return frappe.get_all(
		"Project",
		filters={"name": ["in", names], "is_archived": 0},
		fields=["name", "project_name", "operational_status"],
		order_by="project_name asc",
	)


def _count_if_exists(doctype, filters):
	if not frappe.db.exists("DocType", doctype):
		return 0
	return frappe.db.count(doctype, filters) or 0
