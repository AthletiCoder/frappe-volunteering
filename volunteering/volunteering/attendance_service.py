import frappe
from frappe.utils import getdate, nowdate

from hrms.hr.doctype.attendance.attendance import mark_attendance

from volunteering.volunteering.doctype.daily_work_log.daily_work_log import get_daily_work_log_settings


def process_daily_attendance(attendance_date=None):
	settings = get_daily_work_log_settings()
	if not settings.get("enable_attendance_job"):
		return

	attendance_date = getdate(attendance_date or nowdate())
	employees = get_active_employees(attendance_date)

	for employee in employees:
		try:
			process_employee_attendance(employee, attendance_date)
		except Exception:
			frappe.log_error(
				title=f"Daily attendance failed for {employee}",
				message=frappe.get_traceback(),
			)


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
		ensure_attendance(
			employee=employee,
			attendance_date=attendance_date,
			status="On Leave",
			leave_type=leave.leave_type,
		)
		return

	wfh_request = has_approved_wfh_request(employee, attendance_date)
	work_log = get_submitted_work_log(employee, attendance_date)

	if wfh_request:
		status = "Work From Home" if work_log else "Absent"
		ensure_attendance(employee=employee, attendance_date=attendance_date, status=status)
		return

	if work_log:
		ensure_attendance(employee=employee, attendance_date=attendance_date, status="Present")
		return

	existing = get_submitted_attendance(employee, attendance_date)
	if existing:
		if existing.status == "Work From Home":
			ensure_attendance(employee=employee, attendance_date=attendance_date, status="Absent")
		return

	ensure_attendance(employee=employee, attendance_date=attendance_date, status="Absent")


def ensure_attendance(employee, attendance_date, status, leave_type=None):
	existing = get_submitted_attendance(employee, attendance_date)
	if existing:
		if existing.status == status and (status != "On Leave" or existing.leave_type == leave_type):
			return existing.name

		attendance = frappe.get_doc("Attendance", existing.name)
		update_values = {"status": status}
		if status == "On Leave":
			update_values["leave_type"] = leave_type
		else:
			update_values["leave_type"] = None
			update_values["leave_application"] = None

		attendance.db_set(update_values)
		return attendance.name

	return mark_attendance(
		employee=employee,
		attendance_date=attendance_date,
		status=status,
		leave_type=leave_type,
	)


def get_submitted_attendance(employee, attendance_date):
	name = frappe.db.get_value(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": attendance_date,
			"docstatus": 1,
		},
		"name",
	)
	if not name:
		return None

	return frappe.get_doc("Attendance", name)


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
