import frappe
from frappe.utils import add_days, getdate, nowdate

from hrms.hr.doctype.attendance.attendance import mark_attendance

from volunteering.volunteering.doctype.daily_work_log.daily_work_log import get_daily_work_log_settings


def process_daily_attendance(attendance_date=None, manual=False):
	settings = get_daily_work_log_settings()
	if not manual and not settings.get("enable_attendance_job"):
		return {"skipped": True, "reason": "disabled"}

	# Daily scheduler runs at midnight; finalize the previous day so employees
	# still have the full work day to submit their logs.
	attendance_date = getdate(attendance_date or add_days(nowdate(), -1))
	employees = get_active_employees(attendance_date)

	summary = {
		"attendance_date": str(attendance_date),
		"processed": 0,
		"created": 0,
		"updated": 0,
		"unchanged": 0,
		"skipped": 0,
		"errors": 0,
	}

	for employee in employees:
		try:
			action = process_employee_attendance(employee, attendance_date)
			summary["processed"] += 1
			if action in summary:
				summary[action] += 1
		except Exception:
			summary["errors"] += 1
			frappe.log_error(
				title=f"Daily attendance failed for {employee}",
				message=frappe.get_traceback(),
			)

	return summary


def get_active_employees(attendance_date):
	employees = frappe.get_all(
		"Employee",
		filters={
			"status": "Active",
			"date_of_joining": ["<=", attendance_date],
		},
		fields=["name", "relieving_date"],
	)

	return [
		employee.name
		for employee in employees
		if not employee.relieving_date or getdate(employee.relieving_date) >= attendance_date
	]


def process_employee_attendance(employee, attendance_date):
	leave = get_approved_leave(employee, attendance_date)
	if leave:
		_, action = ensure_attendance(
			employee=employee,
			attendance_date=attendance_date,
			status="On Leave",
			leave_type=leave.leave_type,
		)
		return action

	wfh_request = has_approved_wfh_request(employee, attendance_date)
	work_log = get_submitted_work_log(employee, attendance_date)

	if wfh_request:
		if work_log:
			_, action = ensure_attendance(
				employee=employee, attendance_date=attendance_date, status="Work From Home"
			)
			return action
		if not is_attendance_day_in_progress(attendance_date):
			_, action = ensure_attendance(
				employee=employee, attendance_date=attendance_date, status="Absent"
			)
			return action
		return "skipped"

	if work_log:
		_, action = ensure_attendance(employee=employee, attendance_date=attendance_date, status="Present")
		return action

	if is_attendance_day_in_progress(attendance_date):
		return "skipped"

	existing = get_attendance_record(employee, attendance_date)
	if existing:
		if existing.status == "Work From Home":
			_, action = ensure_attendance(
				employee=employee, attendance_date=attendance_date, status="Absent"
			)
			return action
		return "unchanged"

	_, action = ensure_attendance(employee=employee, attendance_date=attendance_date, status="Absent")
	return action


def ensure_attendance(employee, attendance_date, status, leave_type=None):
	existing = get_attendance_record(employee, attendance_date)
	if existing:
		if _attendance_matches(existing, status, leave_type):
			if existing.docstatus == 0:
				frappe.get_doc("Attendance", existing.name).submit()
				return existing.name, "created"
			return existing.name, "unchanged"

		return _update_attendance(existing.name, status, leave_type), "updated"

	attendance_name = mark_attendance(
		employee=employee,
		attendance_date=attendance_date,
		status=status,
		leave_type=leave_type,
	)
	if attendance_name:
		return attendance_name, "created"

	existing = get_attendance_record(employee, attendance_date)
	if not existing:
		return None, "errors"

	if _attendance_matches(existing, status, leave_type):
		return existing.name, "unchanged"

	return _update_attendance(existing.name, status, leave_type), "updated"


def _attendance_matches(attendance, status, leave_type=None):
	if attendance.status != status:
		return False
	if status == "On Leave":
		return attendance.leave_type == leave_type
	return True


def _update_attendance(attendance_name, status, leave_type=None):
	attendance = frappe.get_doc("Attendance", attendance_name)
	update_values = {"status": status}
	if status == "On Leave":
		update_values["leave_type"] = leave_type
	else:
		update_values["leave_type"] = None
		update_values["leave_application"] = None

	attendance.db_set(update_values)
	if attendance.docstatus == 0:
		attendance.reload()
		attendance.submit()
	return attendance.name


def get_attendance_record(employee, attendance_date):
	for docstatus in (1, 0):
		name = frappe.db.get_value(
			"Attendance",
			{
				"employee": employee,
				"attendance_date": attendance_date,
				"docstatus": docstatus,
			},
			"name",
			order_by="modified desc",
		)
		if name:
			return frappe.get_doc("Attendance", name)
	return None


def get_submitted_attendance(employee, attendance_date):
	attendance = get_attendance_record(employee, attendance_date)
	if attendance and attendance.docstatus == 1:
		return attendance
	return None


def get_submitted_work_log(employee, attendance_date):
	return frappe.db.exists(
		"Daily Work Log",
		{
			"employee": employee,
			"date": attendance_date,
			"docstatus": 1,
		},
	)


def has_approved_wfh_request(employee, attendance_date):
	return frappe.db.exists(
		"Attendance Request",
		{
			"employee": employee,
			"docstatus": 1,
			"reason": "Work From Home",
			"from_date": ["<=", attendance_date],
			"to_date": [">=", attendance_date],
		},
	)


def get_approved_leave(employee, attendance_date):
	return frappe.db.get_value(
		"Leave Application",
		{
			"employee": employee,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ["<=", attendance_date],
			"to_date": [">=", attendance_date],
		},
		["name", "leave_type"],
		as_dict=True,
	)


def has_approved_wfh_request_for_employee(employee, attendance_date):
	return bool(has_approved_wfh_request(employee, attendance_date))


def is_attendance_day_in_progress(attendance_date):
	return getdate(attendance_date) >= getdate(nowdate())
