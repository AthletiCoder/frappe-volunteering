"""HR / Management / Wellness dashboard metrics (informational; not for payroll)."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, date_diff, flt, getdate, nowdate

from volunteering.volunteering.attendance_service import count_special_day_work, get_holiday_info
from volunteering.volunteering.leave_setup import get_fy_dates


@frappe.whitelist()
def get_hr_summary(from_date=None, to_date=None):
	"""Return aggregated HR metrics for dashboards."""
	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or add_days(to_date, -30))

	employees = _active_employees(to_date)
	attendance_rows = frappe.get_all(
		"Attendance",
		filters={
			"docstatus": 1,
			"attendance_date": ["between", [from_date, to_date]],
			"employee": ["in", employees or ["__none__"]],
		},
		fields=["employee", "status", "attendance_date", "working_hours"],
	)

	by_employee = {}
	by_department = {}
	half_day_count = 0
	for row in attendance_rows:
		emp = row.employee
		by_employee.setdefault(emp, {"present": 0, "total": 0})
		by_employee[emp]["total"] += 1
		if row.status in ("Present", "Work From Home", "Half Day"):
			by_employee[emp]["present"] += 1 if row.status != "Half Day" else 0.5
		if row.status == "Half Day":
			half_day_count += 1

		dept = frappe.db.get_value("Employee", emp, "department") or "Unassigned"
		by_department.setdefault(dept, {"present": 0, "total": 0})
		by_department[dept]["total"] += 1
		if row.status in ("Present", "Work From Home"):
			by_department[dept]["present"] += 1
		elif row.status == "Half Day":
			by_department[dept]["present"] += 0.5

	attendance_pct_employee = [
		{
			"employee": emp,
			"employee_name": frappe.db.get_value("Employee", emp, "employee_name"),
			"percentage": round(100 * data["present"] / data["total"], 1) if data["total"] else 0,
		}
		for emp, data in by_employee.items()
	]
	attendance_pct_department = [
		{
			"department": dept,
			"percentage": round(100 * data["present"] / data["total"], 1) if data["total"] else 0,
		}
		for dept, data in by_department.items()
	]

	leave_balances = _leave_balances(employees)
	negative_balances = [row for row in leave_balances if row["balance"] < 0]
	missing_logs = _missing_log_count(employees, from_date, to_date)
	late_submissions = _late_submission_count(from_date, to_date)

	return {
		"from_date": str(from_date),
		"to_date": str(to_date),
		"attendance_pct_by_employee": attendance_pct_employee,
		"attendance_pct_by_department": attendance_pct_department,
		"leave_balances": leave_balances,
		"negative_leave_balances": negative_balances,
		"missing_work_logs": missing_logs,
		"half_day_count": half_day_count,
		"late_log_submissions": late_submissions,
	}


@frappe.whitelist()
def get_management_summary(from_date=None, to_date=None):
	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or add_days(to_date, -30))

	items = frappe.db.sql(
		"""
		SELECT i.project, w.employee, e.department, SUM(i.time_spent_hours) AS hours
		FROM `tabDaily Work Log Item` i
		INNER JOIN `tabDaily Work Log` w ON w.name = i.parent
		INNER JOIN `tabEmployee` e ON e.name = w.employee
		WHERE w.docstatus = 1 AND w.date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY i.project, w.employee, e.department
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	by_project = {}
	by_employee = {}
	by_department = {}
	for row in items:
		hours = flt(row.hours)
		by_project[row.project] = by_project.get(row.project, 0) + hours
		by_employee[row.employee] = by_employee.get(row.employee, 0) + hours
		dept = row.department or "Unassigned"
		by_department[dept] = by_department.get(dept, 0) + hours

	working_days = max(date_diff(to_date, from_date) + 1, 1)
	utilization = [
		{
			"project": project,
			"hours": round(hours, 2),
			"utilization_hours_per_day": round(hours / working_days, 2),
		}
		for project, hours in by_project.items()
	]

	return {
		"hours_by_project": [{"project": k, "hours": round(v, 2)} for k, v in by_project.items()],
		"hours_by_employee": [
			{
				"employee": k,
				"employee_name": frappe.db.get_value("Employee", k, "employee_name"),
				"hours": round(v, 2),
			}
			for k, v in by_employee.items()
		],
		"hours_by_department": [{"department": k, "hours": round(v, 2)} for k, v in by_department.items()],
		"utilization_by_project": utilization,
	}


@frappe.whitelist()
def get_wellness_summary(employee=None):
	"""Informational wellness metrics — never used for payroll."""
	to_date = getdate(nowdate())
	from_date = add_days(to_date, -29)
	employees = [employee] if employee else _active_employees(to_date)

	results = []
	for emp in employees:
		logs = frappe.get_all(
			"Daily Work Log",
			filters={"employee": emp, "docstatus": 1, "date": ["between", [from_date, to_date]]},
			fields=["date", "total_hours"],
		)
		avg_hours = (
			round(sum(flt(l.total_hours) for l in logs) / 30.0, 2) if logs else 0
		)

		last_leave = frappe.db.get_value(
			"Leave Application",
			{"employee": emp, "docstatus": 1, "status": "Approved", "to_date": ["<=", to_date]},
			"to_date",
			order_by="to_date desc",
		)
		days_since_leave = date_diff(to_date, last_leave) if last_leave else None

		holiday_work = 0
		weekly_off_work = 0
		for log in logs:
			info = get_holiday_info(emp, log.date)
			if not info or flt(log.total_hours) <= 0:
				continue
			if info.get("weekly_off"):
				weekly_off_work += 1
			else:
				holiday_work += 1

		results.append(
			{
				"employee": emp,
				"employee_name": frappe.db.get_value("Employee", emp, "employee_name"),
				"avg_hours_per_day_30": avg_hours,
				"days_since_last_leave": days_since_leave,
				"holiday_work_count": holiday_work,
				"weekly_off_work_count": weekly_off_work,
			}
		)

	return results


def _active_employees(as_of):
	rows = frappe.get_all(
		"Employee",
		filters={"status": "Active", "date_of_joining": ["<=", as_of]},
		fields=["name", "relieving_date"],
	)
	return [
		r.name for r in rows if not r.relieving_date or getdate(r.relieving_date) >= getdate(as_of)
	]


def _leave_balances(employees):
	leave_type = (
		frappe.db.get_single_value("Leave Policy Settings", "default_leave_type") or "Privilege Leave"
	)
	fy_start, fy_end = get_fy_dates()
	results = []
	for emp in employees:
		try:
			from hrms.hr.doctype.leave_application.leave_application import get_leave_details

			details = get_leave_details(emp, nowdate())
			leave_allocation = (details or {}).get("leave_allocation") or {}
			info = leave_allocation.get(leave_type) or {}
			balance = flt(info.get("remaining_leaves"))
		except Exception:
			balance = 0
		results.append(
			{
				"employee": emp,
				"employee_name": frappe.db.get_value("Employee", emp, "employee_name"),
				"leave_type": leave_type,
				"balance": balance,
				"fy_start": str(fy_start),
				"fy_end": str(fy_end),
			}
		)
	return results


def _missing_log_count(employees, from_date, to_date):
	from datetime import timedelta

	count = 0
	current = getdate(from_date)
	end = getdate(to_date)
	while current <= end:
		for emp in employees:
			if get_holiday_info(emp, current):
				continue
			if frappe.db.exists(
				"Leave Application",
				{
					"employee": emp,
					"docstatus": 1,
					"status": "Approved",
					"from_date": ["<=", current],
					"to_date": [">=", current],
				},
			):
				continue
			if not frappe.db.exists(
				"Daily Work Log",
				{"employee": emp, "date": current, "docstatus": 1},
			):
				count += 1
		current += timedelta(days=1)
	return count


def _late_submission_count(from_date, to_date):
	"""Logs submitted after next-day noon relative to work date."""
	logs = frappe.get_all(
		"Daily Work Log",
		filters={"docstatus": 1, "date": ["between", [from_date, to_date]]},
		fields=["date", "modified", "creation"],
	)
	late = 0
	for log in logs:
		submitted_at = getdate(log.modified)  # approximate; use creation if needed
		# Prefer submission timestamp from modified after submit
		from frappe.utils import get_datetime

		deadline = get_datetime(f"{add_days(log.date, 1)} 12:00:00")
		if get_datetime(log.modified) > deadline:
			late += 1
	return late
