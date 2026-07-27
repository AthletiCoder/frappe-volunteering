"""Work log summary email (daily / weekly / monthly) for leadership.

Daily digest keeps the detailed per-employee table (attendance, projects,
tasks, comments, manager notes). Weekly / monthly digests aggregate hours and
logged-day counts across the period. Recipients, sender and frequency are all
configured on **Daily Work Log Settings**.
"""

from __future__ import annotations

import frappe
from frappe.utils import (
	add_days,
	flt,
	formatdate,
	get_first_day,
	get_last_day,
	getdate,
	nowdate,
)

from volunteering.volunteering.doctype.daily_work_log.daily_work_log import (
	get_daily_work_log_settings,
)

BOARD_ROLES = ("Executive Board Member", "Executive Board Chairperson")
PRESENT_THRESHOLD = 6.0


# ---------------------------------------------------------------------------
# Scheduler / entrypoints
# ---------------------------------------------------------------------------
def run_noon_attendance_jobs():
	"""Process yesterday's attendance then email the work log summary (if due)."""
	from volunteering.volunteering.attendance_service import process_daily_attendance

	summary = process_daily_attendance()
	digest = send_work_log_digest()
	return {"attendance": summary, "digest": digest}


def send_work_log_digest(reference_date=None, force=False):
	"""Send the configured work log summary.

	Runs from the daily noon cron; only actually emails when the configured
	frequency is due for `reference_date` (unless `force`).
	"""
	settings = get_daily_work_log_settings()
	if not settings.get("enable_board_digest", 1) and not force:
		return {"skipped": True, "reason": "disabled"}

	reference_date = getdate(reference_date or nowdate())
	frequency = (settings.get("digest_frequency") or "Daily").strip() or "Daily"

	if not force and not _is_due(frequency, reference_date):
		return {"skipped": True, "reason": "not due", "frequency": frequency}

	recipients = _digest_recipients(settings)
	if not recipients:
		return {"skipped": True, "reason": "no recipients"}

	start, end, label = _resolve_period(frequency, reference_date)

	if frequency == "Daily":
		rows = _build_rows(start)
		html = _render_html(start, rows)
		count = len(rows)
	else:
		rows = _period_rows(start, end)
		html = _render_period_html(label, start, end, rows)
		count = len(rows)

	subject = f"Work Log Summary — {label} ({count} employees)"
	sender = (settings.get("digest_sender") or "").strip() or None

	frappe.sendmail(
		recipients=recipients,
		sender=sender,
		subject=subject,
		message=html,
		delayed=not force,
	)
	return {
		"recipients": recipients,
		"rows": count,
		"frequency": frequency,
		"period": {"from": str(start), "to": str(end), "label": label},
	}


# Backwards-compatible alias (older cron config / callers).
def send_attendance_board_digest(attendance_date=None):
	settings = get_daily_work_log_settings()
	frequency = (settings.get("digest_frequency") or "Daily").strip() or "Daily"
	# Preserve the historical "always daily" behaviour for direct callers.
	if frequency == "Daily":
		return send_work_log_digest(reference_date=attendance_date, force=True)
	return send_work_log_digest(reference_date=attendance_date)


@frappe.whitelist()
def send_work_log_digest_now():
	"""Manual 'Send now' from the settings page (respects configured frequency period)."""
	frappe.only_for(("System Manager", "HR Manager", "HR User"))
	return send_work_log_digest(force=True)


@frappe.whitelist()
def preview_work_log_digest():
	"""Return the rendered HTML + recipients for the settings-page preview dialog."""
	frappe.only_for(("System Manager", "HR Manager", "HR User"))
	settings = get_daily_work_log_settings()
	frequency = (settings.get("digest_frequency") or "Daily").strip() or "Daily"
	start, end, label = _resolve_period(frequency, getdate(nowdate()))

	if frequency == "Daily":
		rows = _build_rows(start)
		html = _render_html(start, rows)
	else:
		rows = _period_rows(start, end)
		html = _render_period_html(label, start, end, rows)

	return {
		"html": html,
		"recipients": _digest_recipients(settings),
		"frequency": frequency,
		"label": label,
	}


# ---------------------------------------------------------------------------
# Frequency helpers
# ---------------------------------------------------------------------------
def _is_due(frequency, reference_date):
	if frequency == "Weekly":
		return getdate(reference_date).weekday() == 0  # Monday
	if frequency == "Monthly":
		return getdate(reference_date).day == 1
	return True  # Daily


def _resolve_period(frequency, reference_date):
	"""Return (start, end, human_label) for the period the digest should cover."""
	reference_date = getdate(reference_date)
	if frequency == "Weekly":
		# Previous Monday..Sunday relative to reference_date.
		this_monday = add_days(reference_date, -reference_date.weekday())
		start = add_days(this_monday, -7)
		end = add_days(this_monday, -1)
		return start, end, f"Week of {formatdate(start)} – {formatdate(end)}"
	if frequency == "Monthly":
		last_month_end = add_days(get_first_day(reference_date), -1)
		start = get_first_day(last_month_end)
		end = get_last_day(last_month_end)
		return start, end, formatdate(start, "MMMM yyyy")
	day = add_days(reference_date, -1)
	return day, day, formatdate(day)


# ---------------------------------------------------------------------------
# Recipients
# ---------------------------------------------------------------------------
def _digest_recipients(settings) -> list[str]:
	emails = set()
	raw = (settings.get("board_digest_extra_recipients") or "").replace("\n", ",")
	for part in raw.split(","):
		email = part.strip()
		if email and "@" in email:
			emails.add(email)

	roles = _recipient_roles(settings)
	if roles:
		users = frappe.get_all(
			"Has Role",
			filters={"role": ["in", roles], "parenttype": "User"},
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


def _recipient_roles(settings) -> list[str]:
	raw = settings.get("digest_recipient_roles")
	if raw is None:
		return list(BOARD_ROLES)
	roles = [r.strip() for r in raw.replace(",", "\n").split("\n") if r.strip()]
	return roles or list(BOARD_ROLES)


# ---------------------------------------------------------------------------
# Daily (detailed) rows
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Weekly / monthly (aggregated) rows
# ---------------------------------------------------------------------------
def _period_rows(start, end):
	from volunteering.volunteering.employment_type import UNPAID_EMPLOYMENT_TYPE

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", "date_of_joining": ["<=", end]},
		fields=["name", "employee_name", "department", "relieving_date", "employment_type"],
		order_by="employee_name asc",
	)
	rows = []
	for emp in employees:
		if emp.employment_type == UNPAID_EMPLOYMENT_TYPE:
			continue
		if emp.relieving_date and emp.relieving_date < start:
			continue

		logs = frappe.get_all(
			"Daily Work Log",
			filters={
				"employee": emp.name,
				"docstatus": 1,
				"date": ["between", [start, end]],
			},
			fields=["name", "total_hours"],
		)
		total_hours = sum(flt(log.total_hours) for log in logs)
		days_logged = len(logs)

		projects = set()
		if logs:
			items = frappe.get_all(
				"Daily Work Log Item",
				filters={"parent": ["in", [log.name for log in logs]]},
				fields=["project"],
			)
			projects = {i.project for i in items if i.project}

		rows.append(
			{
				"employee_name": emp.employee_name or emp.name,
				"department": emp.department or "",
				"days_logged": days_logged,
				"total_hours": total_hours,
				"avg_hours": (total_hours / days_logged) if days_logged else 0,
				"projects": ", ".join(sorted(projects)),
				"no_log": days_logged == 0,
			}
		)
	return rows


# ---------------------------------------------------------------------------
# Rendering (email-safe inline styles)
# ---------------------------------------------------------------------------
_WRAP_OPEN = (
	"<div style=\"font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
	"color:#1f2733;max-width:760px;margin:0 auto;\">"
)
_WRAP_CLOSE = "</div>"


def _stat_chip(label, value, color):
	return (
		f"<td style='padding:0 8px;'>"
		f"<div style='background:{color}1a;border:1px solid {color}33;border-radius:10px;"
		f"padding:10px 14px;text-align:center;'>"
		f"<div style='font-size:20px;font-weight:700;color:{color};'>{value}</div>"
		f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#64748b;'>{label}</div>"
		f"</div></td>"
	)


def _header_block(title, subtitle):
	return (
		"<div style='border-bottom:3px solid #2563eb;padding-bottom:12px;margin-bottom:16px;'>"
		f"<div style='font-size:22px;font-weight:700;color:#0f172a;'>{title}</div>"
		f"<div style='font-size:13px;color:#64748b;margin-top:2px;'>{subtitle}</div>"
		"</div>"
	)


def _th(text, align="left"):
	return (
		f"<th style='text-align:{align};padding:8px 10px;font-size:11px;text-transform:uppercase;"
		f"letter-spacing:.03em;color:#475569;border-bottom:2px solid #e2e8f0;'>{text}</th>"
	)


def _td(text, align="left", bold=False):
	weight = "600" if bold else "400"
	return (
		f"<td style='text-align:{align};padding:8px 10px;font-size:13px;color:#1f2733;"
		f"border-bottom:1px solid #eef2f7;font-weight:{weight};'>{text}</td>"
	)


def _render_html(attendance_date, rows):
	esc = frappe.utils.escape_html
	missing = sum(1 for r in rows if r["missing_log"])
	low = sum(1 for r in rows if r["low_hours"])
	total_hours = sum(flt(r["hours"]) for r in rows)

	parts = [
		_WRAP_OPEN,
		_header_block("Work Log Summary", f"Daily · {formatdate(attendance_date)}"),
		"<table style='width:100%;border-collapse:collapse;margin-bottom:18px;'><tr>",
		_stat_chip("Employees", len(rows), "#2563eb"),
		_stat_chip("Total Hours", f"{total_hours:g}", "#0891b2"),
		_stat_chip("Low Hours", low, "#d97706"),
		_stat_chip("Missing Logs", missing, "#dc2626"),
		"</tr></table>",
		"<table style='width:100%;border-collapse:collapse;'>",
		"<thead><tr>",
		_th("Employee"),
		_th("Attendance"),
		_th("Hours", "right"),
		_th("Projects"),
		_th("Tasks"),
		_th("Comments"),
		_th("Manager Notes"),
		_th("Leave"),
		"</tr></thead><tbody>",
	]
	for row in rows:
		bg = ""
		if row["missing_log"] or row["pending_leave"]:
			bg = "background:#fef2f2;"
		elif row["low_hours"]:
			bg = "background:#fffbeb;"
		parts.append(f"<tr style='{bg}'>")
		parts.append(_td(esc(row["employee_name"]), bold=True))
		parts.append(_td(esc(str(row["status"]))))
		parts.append(_td(f"{flt(row['hours']):g}", "right"))
		parts.append(_td(esc(row["project_breakdown"]) or "—"))
		parts.append(_td(esc(row["task_summary"]) or "—"))
		parts.append(_td(esc(row["comments"]) or "—"))
		parts.append(_td(esc(row["manager_notes"]) or "—"))
		parts.append(_td(esc(row["leave_status"]) or "—"))
		parts.append("</tr>")
	parts.append("</tbody></table>")
	parts.append(_legend("Amber = below 6h · Red = missing log or pending leave approval."))
	parts.append(_WRAP_CLOSE)
	return "\n".join(parts)


def _render_period_html(label, start, end, rows):
	esc = frappe.utils.escape_html
	no_log = sum(1 for r in rows if r["no_log"])
	total_hours = sum(flt(r["total_hours"]) for r in rows)
	active = sum(1 for r in rows if not r["no_log"])

	parts = [
		_WRAP_OPEN,
		_header_block(
			"Work Log Summary",
			f"{label} · {formatdate(start)} – {formatdate(end)}",
		),
		"<table style='width:100%;border-collapse:collapse;margin-bottom:18px;'><tr>",
		_stat_chip("Employees", len(rows), "#2563eb"),
		_stat_chip("Logged", active, "#059669"),
		_stat_chip("Total Hours", f"{total_hours:g}", "#0891b2"),
		_stat_chip("No Logs", no_log, "#dc2626"),
		"</tr></table>",
		"<table style='width:100%;border-collapse:collapse;'>",
		"<thead><tr>",
		_th("Employee"),
		_th("Department"),
		_th("Days Logged", "right"),
		_th("Total Hours", "right"),
		_th("Avg / Day", "right"),
		_th("Projects"),
		"</tr></thead><tbody>",
	]
	for row in rows:
		bg = "background:#fef2f2;" if row["no_log"] else ""
		parts.append(f"<tr style='{bg}'>")
		parts.append(_td(esc(row["employee_name"]), bold=True))
		parts.append(_td(esc(row["department"]) or "—"))
		parts.append(_td(str(row["days_logged"]), "right"))
		parts.append(_td(f"{flt(row['total_hours']):g}", "right"))
		parts.append(_td(f"{flt(row['avg_hours']):.1f}", "right"))
		parts.append(_td(esc(row["projects"]) or "—"))
		parts.append("</tr>")
	parts.append("</tbody></table>")
	parts.append(_legend("Red = no work logs submitted in this period."))
	parts.append(_WRAP_CLOSE)
	return "\n".join(parts)


def _legend(text):
	return (
		f"<p style='font-size:12px;color:#94a3b8;margin-top:14px;'>{text}</p>"
	)
