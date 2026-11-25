import frappe
from frappe.utils import add_days, flt, get_datetime, getdate, now_datetime, nowdate

from hrms.hr.doctype.attendance.attendance import mark_attendance
from hrms.hr.utils import get_holidays_for_employee

from volunteering.volunteering.doctype.daily_work_log.daily_work_log import get_daily_work_log_settings
from volunteering.volunteering.leave_setup import WEEKLY_OFF_DAY

PRESENT_HOURS_THRESHOLD = 6.0


def get_present_hours_threshold(day=None):
	from volunteering.volunteering.hr_policy import policy_on
	if policy_on(day).get("_revision"):
		return policy_on(day)["full_day_hours"]
	settings = get_daily_work_log_settings()
	return flt(settings.get("present_hours_threshold") or PRESENT_HOURS_THRESHOLD)


def process_daily_attendance(attendance_date=None, manual=False):
	explicit_date = attendance_date is not None
	settings = get_daily_work_log_settings()
	if not manual and not settings.get("enable_attendance_job"):
		return {"skipped": True, "reason": "disabled"}

	# Revisit the open logging window and the day whose grace just ended.
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

	from volunteering.volunteering.hr_policy import policy_on
	dates = [attendance_date] if manual or explicit_date else [getdate(add_days(nowdate(), -offset)) for offset in range(1, max(3, policy_on()["work_log_days"] + 2))]
	for employee in employees:
		try:
			for day in dates:
				action = process_employee_attendance(employee, day)
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


def refresh_attendance_for_work_log(doc, method=None):
	"""Recompute attendance when a Daily Work Log is submitted, updated, or cancelled."""
	if not doc.employee or not doc.date:
		return
	# Submitted (1) or Cancelled (2) — cancelled logs must recompute without their hours
	if cint_docstatus(doc) not in (1, 2):
		return

	try:
		process_employee_attendance(doc.employee, doc.date, force_regularized=False)
	except Exception:
		frappe.log_error(
			title=f"Attendance refresh failed for {doc.name}",
			message=frappe.get_traceback(),
		)


def cint_docstatus(doc):
	return int(doc.docstatus or 0)


def get_active_employees(attendance_date):
	from volunteering.volunteering.hr_policy import applies_to_employee, policy_on

	employees = frappe.get_all(
		"Employee",
		filters={
			"status": "Active",
			"date_of_joining": ["<=", attendance_date],
		},
		fields=["name", "relieving_date", "employment_type"],
	)

	return [
		employee.name
		for employee in employees
		if applies_to_employee(employee.name, attendance_date)
		and (not employee.relieving_date or getdate(employee.relieving_date) >= attendance_date)
	]


def process_employee_attendance(employee, attendance_date, force_regularized=False):
	attendance_date = getdate(attendance_date)
	from volunteering.volunteering.hr_policy import applies_to_employee, policy_on
	if not applies_to_employee(employee, attendance_date): return "skipped"
	person = frappe.db.get_value("Employee", employee, ["date_of_joining", "relieving_date"], as_dict=True)
	if not person or (person.date_of_joining and attendance_date < getdate(person.date_of_joining)) or (person.relieving_date and attendance_date > getdate(person.relieving_date)): return "skipped"
	from volunteering.volunteering.hr_leave_balances import salary_processed
	if salary_processed(employee, attendance_date, attendance_date):
		return "skipped"

	if not force_regularized and has_approved_regularization(employee, attendance_date):
		return "skipped"

	leave = get_approved_leave(employee, attendance_date)
	if leave:
		from volunteering.volunteering.employee_calendars import holiday_on
		if holiday_on(employee, attendance_date):
			return ensure_attendance(employee, attendance_date, "Holiday", working_hours=get_submitted_work_log_hours(employee, attendance_date))[1]
		half = bool(leave.get("half_day") and getdate(leave.get("half_day_date") or leave.from_date) == attendance_date)
		hours = get_submitted_work_log_hours(employee, attendance_date)
		_, action = ensure_attendance(
			employee=employee,
			attendance_date=attendance_date,
			status="Half Day" if half else "On Leave",
			leave_type=leave.leave_type,
			working_hours=hours if half else 0,
			half_day_status="Present" if half and hours > 0 and hours >= policy_on(attendance_date)["half_day_hours"] else ("Absent" if half else None),
		)
		return action

	# Holiday list weekly offs, plus org Wednesday off even if the list is missing.
	if get_holiday_info(employee, attendance_date):
		hours = get_submitted_work_log_hours(employee, attendance_date)
		_, action = ensure_attendance(
			employee=employee,
			attendance_date=attendance_date,
			status="Holiday",
			working_hours=hours,
		)
		return action

	wfh_request = has_approved_wfh_request(employee, attendance_date)
	hours = get_submitted_work_log_hours(employee, attendance_date)
	grace_open = is_grace_period_open(attendance_date)
	pending_leave = frappe.db.exists("Leave Application", {"employee": employee, "docstatus": 0, "status": "Open", "from_date": ["<=", attendance_date], "to_date": [">=", attendance_date]})

	if wfh_request:
		if hours >= get_present_hours_threshold(attendance_date):
			_, action = ensure_attendance(
				employee=employee,
				attendance_date=attendance_date,
				status="Work From Home",
				working_hours=hours,
			)
			return action
		if hours > 0 and hours >= policy_on(attendance_date)["half_day_hours"]:
			return ensure_attendance(employee, attendance_date, "Half Day", working_hours=hours, half_day_status="Absent")[1]
		if grace_open or pending_leave:
			return "skipped"
		_, action = ensure_attendance(
			employee=employee,
			attendance_date=attendance_date,
			status="Absent",
			working_hours=0,
		)
		return action

	if hours >= get_present_hours_threshold(attendance_date):
		_, action = ensure_attendance(
			employee=employee,
			attendance_date=attendance_date,
			status="Present",
			working_hours=hours,
		)
		return action

	if hours > 0 and hours >= policy_on(attendance_date)["half_day_hours"]:
		_, action = ensure_attendance(
			employee=employee,
			attendance_date=attendance_date,
			status="Half Day",
			working_hours=hours,
			half_day_status="Absent",
		)
		return action

	if grace_open:
		return "skipped"
	if pending_leave:
		return "skipped"  # A filed leave request needs a decision, not an unpaid assumption.

	_, action = ensure_attendance(
		employee=employee,
		attendance_date=attendance_date,
		status="Absent",
		working_hours=hours,
	)
	return action


def ensure_attendance(
	employee,
	attendance_date,
	status,
	leave_type=None,
	working_hours=None,
	half_day_status=None,
):
	existing = get_attendance_record(employee, attendance_date)
	if existing:
		if _attendance_matches(existing, status, leave_type, working_hours, half_day_status):
			if existing.docstatus == 0:
				frappe.get_doc("Attendance", existing.name).submit()
				_set_working_hours(existing.name, working_hours)
				return existing.name, "created"
			_set_working_hours(existing.name, working_hours)
			return existing.name, "unchanged"

		return (
			_update_attendance(existing.name, status, leave_type, working_hours, half_day_status),
			"updated",
		)

	attendance_name = _create_attendance(
		employee=employee,
		attendance_date=attendance_date,
		status=status,
		leave_type=leave_type,
		working_hours=working_hours,
		half_day_status=half_day_status,
	)
	if attendance_name:
		return attendance_name, "created"

	existing = get_attendance_record(employee, attendance_date)
	if not existing:
		return None, "errors"

	if _attendance_matches(existing, status, leave_type, working_hours, half_day_status):
		_set_working_hours(existing.name, working_hours)
		return existing.name, "unchanged"

	return (
		_update_attendance(existing.name, status, leave_type, working_hours, half_day_status),
		"updated",
	)


def _create_attendance(
	employee,
	attendance_date,
	status,
	leave_type=None,
	working_hours=None,
	half_day_status=None,
):
	"""Create attendance; ignore leave_type mandatory for hours-based Half Day / Holiday."""
	savepoint = f"ngo_att_{frappe.generate_hash(length=8)}"
	try:
		frappe.db.savepoint(savepoint)
		attendance = frappe.new_doc("Attendance")
		attendance.employee = employee
		attendance.attendance_date = attendance_date
		attendance.status = status
		attendance.leave_type = leave_type
		if status == "Half Day":
			attendance.half_day_status = half_day_status or "Present"
		attendance.insert(ignore_permissions=True, ignore_mandatory=True)
		attendance.submit()
		_set_working_hours(attendance.name, working_hours)
		return attendance.name
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		# Fall back to standard API for common statuses
		try:
			name = mark_attendance(
				employee=employee,
				attendance_date=attendance_date,
				status=status,
				leave_type=leave_type,
				half_day_status=half_day_status,
			)
			if name:
				_set_working_hours(name, working_hours)
			return name
		except Exception:
			frappe.log_error(
				title=f"Could not create attendance for {employee} on {attendance_date}",
				message=frappe.get_traceback(),
			)
			return None


def _attendance_matches(attendance, status, leave_type=None, working_hours=None, half_day_status=None):
	if attendance.status != status:
		return False
	if status == "On Leave" and attendance.leave_type != leave_type:
		return False
	if status == "Half Day" and half_day_status and attendance.half_day_status != half_day_status:
		return False
	if working_hours is not None and flt(attendance.working_hours) != flt(working_hours):
		return False
	return True


def _update_attendance(attendance_name, status, leave_type=None, working_hours=None, half_day_status=None):
	attendance = frappe.get_doc("Attendance", attendance_name)
	update_values = {"status": status}
	if status == "On Leave":
		update_values["leave_type"] = leave_type
	else:
		update_values["leave_type"] = None
		update_values["leave_application"] = None

	if status == "Half Day":
		update_values["half_day_status"] = half_day_status or "Present"
	else:
		update_values["half_day_status"] = None

	attendance.db_set(update_values)
	_set_working_hours(attendance_name, working_hours)
	if attendance.docstatus == 0:
		attendance.reload()
		attendance.submit()
	return attendance.name


def _set_working_hours(attendance_name, working_hours):
	if working_hours is None or not attendance_name:
		return
	frappe.db.set_value("Attendance", attendance_name, "working_hours", flt(working_hours), update_modified=False)


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


def get_submitted_work_log(employee, attendance_date):
	return frappe.db.get_value(
		"Daily Work Log",
		{
			"employee": employee,
			"date": attendance_date,
			"docstatus": 1,
		},
		["name", "total_hours"],
		as_dict=True,
	)


def get_submitted_work_log_hours(employee, attendance_date):
	log = get_submitted_work_log(employee, attendance_date)
	return flt(log.total_hours) if log else 0.0


def has_approved_wfh_request(employee, attendance_date):
	if frappe.db.exists("DocType", "Staff Time Request") and frappe.db.exists("Staff Time Request", {
		"employee": employee, "request_type": "WFH", "status": "Approved", "from_date": ["<=", attendance_date], "to_date": [">=", attendance_date]}):
		return True
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


@frappe.whitelist()
def has_approved_wfh_request_for_employee(employee, attendance_date):
	return bool(has_approved_wfh_request(employee, attendance_date))


def has_approved_regularization(employee, attendance_date):
	if not frappe.db.exists("DocType", "Attendance Regularization Request"):
		return False
	if frappe.db.exists(
		"Attendance Regularization Request",
		{
			"employee": employee,
			"attendance_date": attendance_date,
			"docstatus": 1,
			"status": "Approved",
		},
	):
		return True
	if frappe.db.has_column("Attendance", "custom_regularized"):
		return bool(
			frappe.db.get_value(
				"Attendance",
				{
					"employee": employee,
					"attendance_date": attendance_date,
					"docstatus": 1,
					"custom_regularized": 1,
				},
			)
		)
	return False


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
		["name", "leave_type", "half_day", "half_day_date", "from_date"],
		as_dict=True,
	)


def is_org_weekly_off(attendance_date) -> bool:
	"""Org weekly off is Wednesday (see leave_setup.WEEKLY_OFF_DAY)."""
	from volunteering.volunteering.hr_policy import policy_on
	return getdate(attendance_date).weekday() == policy_on(attendance_date)["weekly_off_day"]


def get_holiday_info(employee, attendance_date):
	"""Return holiday row for date, or None. Includes weekly offs."""
	attendance_date = getdate(attendance_date)
	from volunteering.volunteering.hr_policy import policy_on
	if policy_on(attendance_date).get("_revision"):
		from volunteering.volunteering.employee_calendars import holiday_on
		return holiday_on(employee, attendance_date)
	holidays = get_holidays_for_employee(
		employee, attendance_date, attendance_date, raise_exception=False
	)
	if not holidays:
		if is_org_weekly_off(attendance_date):
			return {"holiday_date": attendance_date, "weekly_off": 1, "description": "Weekly Off"}
		return None

	holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
	if not holiday_list:
		from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

		holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)

	if not holiday_list:
		return {"holiday_date": attendance_date, "weekly_off": 0, "description": "Holiday"}

	row = frappe.db.get_value(
		"Holiday",
		{"parent": holiday_list, "holiday_date": attendance_date},
		["holiday_date", "weekly_off", "description"],
		as_dict=True,
	)
	return row or {"holiday_date": attendance_date, "weekly_off": 0, "description": "Holiday"}


def is_weekly_off(employee, attendance_date):
	info = get_holiday_info(employee, attendance_date)
	return bool(info and info.get("weekly_off"))


def is_grace_period_open(attendance_date):
	"""Employees may complete logs until next day 12:00 PM."""
	attendance_date = getdate(attendance_date)
	from volunteering.volunteering.hr_policy import policy_on, deadline_for_log
	policy = policy_on(attendance_date)
	deadline = get_datetime(deadline_for_log(attendance_date, policy)) if policy.get("_revision") else get_datetime(f"{add_days(attendance_date, 1)} 12:00:00")
	return now_datetime() < deadline


def is_attendance_day_in_progress(attendance_date):
	"""Backward-compatible alias: true while grace period is still open."""
	return is_grace_period_open(attendance_date)


def count_special_day_work(employee, from_date, to_date, weekly_off_only=False):
	"""Count days with submitted hours on holiday or weekly off (derived, not stored)."""
	logs = frappe.get_all(
		"Daily Work Log",
		filters={
			"employee": employee,
			"docstatus": 1,
			"date": ["between", [from_date, to_date]],
			"total_hours": [">", 0],
		},
		fields=["date"],
	)
	count = 0
	for log in logs:
		info = get_holiday_info(employee, log.date)
		if not info:
			continue
		if weekly_off_only and not info.get("weekly_off"):
			continue
		if not weekly_off_only and info.get("weekly_off"):
			continue
		count += 1
	return count
