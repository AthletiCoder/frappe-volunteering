"""Daily attendance digest email for Executive Board."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, flt, formatdate, nowdate

from volunteering.volunteering.doctype.daily_work_log.daily_work_log import get_daily_work_log_settings

BOARD_ROLES = ("Executive Board Member", "Executive Board Chairperson")
PRESENT_THRESHOLD = 6.0


def send_attendance_board_digest(attendance_date=None):
	settings = get_daily_work_log_settings()
	if not settings.get("enable_board_digest", 1):
		return {"skipped": True, "reason": "disabled"}

	recipients = _digest_recipients(settings)
	if not recipients:
		return {"skipped": True, "reason": "no recipients"}

	attendance_date = attendance_date or add_days(nowdate(), -1)
	rows = _build_rows(attendance_date)
	subject = f"Attendance digest {formatdate(attendance_date)} — {len(rows)} employees"

	html = _render_html(attendance_date, rows)
	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=html,
		delayed=True,
	)
	return {"recipients": recipients, "rows": len(rows), "attendance_date": str(attendance_date)}


def run_noon_attendance_jobs():
	"""Process yesterday's attendance then email the board."""
	from volunteering.volunteering.attendance_service import process_daily_attendance

	summary = process_daily_attendance()
	digest = send_attendance_board_digest()
	return {"attendance": summary, "digest": digest}


def _digest_recipients(settings) -> list[str]:
	emails = set()
	raw = (settings.get("board_digest_extra_recipients") or "").replace("\n", ",")
	for part in raw.split(","):
		email = part.strip()
		if email and "@" in email:
			emails.add(email)

	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", list(BOARD_ROLES)], "parenttype": "User"},
		fields=["parent"],
		distinct=True,
	)
	for row in users:
		user = row.parent
		if user in ("Administrator", "Guest"):
			continue
		info = frappe.db.get_value("User", user, ["enabled", "email"], as_dict=True)
		if info and info.enabled and info.email:
			emails.add(info.email)

	return sorted(emails)


def _build_rows(attendance_date):
	from volunteering.volunteering.employment_type import UNPAID_EMPLOYMENT_TYPE

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", "date_of_joining": ["<=", attendance_date]},
		fields=["name", "employee_name", "department", "relieving_date", "employment_type"],
	)
	rows = []
	for emp in employees:
		if emp.employment_type == UNPAID_EMPLOYMENT_TYPE:
			continue
		if emp.relieving_date and emp.relieving_date < attendance_date:
			continue
		rows.append(_row_for_employee(emp, attendance_date))
	return rows


def _row_for_employee(emp, attendance_date):
	attendance = frappe.db.get_value(
		"Attendance",
		{"employee": emp.name, "attendance_date": attendance_date, "docstatus": 1},
		["status", "working_hours"],
		as_dict=True,
	)
	work_log = frappe.db.get_value(
		"Daily Work Log",
		{"employee": emp.name, "date": attendance_date, "docstatus": 1},
		["name", "total_hours", "notes"],
		as_dict=True,
	)

	project_breakdown = ""
	task_summary = ""
	if work_log:
		items = frappe.get_all(
			"Daily Work Log Item",
			filters={"parent": work_log.name},
			fields=["project", "task_title", "time_spent_hours", "description"],
		)
		parts = []
		tasks = []
		for item in items:
			parts.append(f"{item.project}: {flt(item.time_spent_hours):g}h")
			tasks.append(item.task_title or (item.description or "")[:40])
		project_breakdown = "; ".join(parts)
		task_summary = "; ".join(tasks)

	manager_notes = ""
	if frappe.db.exists("DocType", "Manager Note"):
		notes = frappe.get_all(
			"Manager Note",
			filters={"employee": emp.name, "note_date": attendance_date},
			fields=["note_type", "content"],
			order_by="creation asc",
		)
		manager_notes = " | ".join(f"[{n.note_type}] {n.content}" for n in notes)

	leave_status = ""
	pending_leave = frappe.db.exists(
		"Leave Application",
		{
			"employee": emp.name,
			"docstatus": 0,
			"status": "Open",
			"from_date": ["<=", attendance_date],
			"to_date": [">=", attendance_date],
		},
	)
	approved_leave = frappe.db.exists(
		"Leave Application",
		{
			"employee": emp.name,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ["<=", attendance_date],
			"to_date": [">=", attendance_date],
		},
	)
	if approved_leave:
		leave_status = "On Leave"
	elif pending_leave:
		leave_status = "Pending Approval"

	hours = flt(work_log.total_hours) if work_log else flt(attendance.working_hours if attendance else 0)
	status = attendance.status if attendance else ("—" if not work_log else "Pending")
	missing_log = not work_log and status not in ("On Leave", "Holiday")
	low_hours = bool(work_log) and hours < PRESENT_THRESHOLD and status not in ("On Leave", "Holiday")

	return {
		"employee_name": emp.employee_name or emp.name,
		"status": status,
		"hours": hours,
		"project_breakdown": project_breakdown,
		"task_summary": task_summary,
		"comments": (work_log.notes if work_log else "") or "",
		"manager_notes": manager_notes,
		"leave_status": leave_status,
		"missing_log": missing_log,
		"low_hours": low_hours,
		"pending_leave": bool(pending_leave),
	}


def _render_html(attendance_date, rows):
	highlight = "background:#fff3cd;"
	danger = "background:#f8d7da;"

	lines = [
		f"<p><b>Date:</b> {formatdate(attendance_date)}</p>",
		"<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-size:13px;'>",
		"<thead><tr>"
		"<th>Employee</th><th>Attendance</th><th>Hours</th><th>Projects</th>"
		"<th>Tasks</th><th>Comments</th><th>Manager Notes</th><th>Leave</th>"
		"</tr></thead><tbody>",
	]
	for row in rows:
		style = ""
		if row["missing_log"] or row["pending_leave"]:
			style = danger
		elif row["low_hours"]:
			style = highlight
		lines.append(
			f"<tr style='{style}'>"
			f"<td>{frappe.utils.escape_html(row['employee_name'])}</td>"
			f"<td>{frappe.utils.escape_html(str(row['status']))}</td>"
			f"<td>{row['hours']:g}</td>"
			f"<td>{frappe.utils.escape_html(row['project_breakdown'])}</td>"
			f"<td>{frappe.utils.escape_html(row['task_summary'])}</td>"
			f"<td>{frappe.utils.escape_html(row['comments'])}</td>"
			f"<td>{frappe.utils.escape_html(row['manager_notes'])}</td>"
			f"<td>{frappe.utils.escape_html(row['leave_status'])}</td>"
			"</tr>"
		)
	lines.append("</tbody></table>")
	lines.append(
		"<p style='font-size:12px;color:#666;'>"
		"Yellow = hours below 6. Red = missing log or pending leave approval."
		"</p>"
	)
	return "\n".join(lines)
