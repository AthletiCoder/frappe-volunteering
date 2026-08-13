"""Flip wrongly marked Absent attendance on org weekly off (Wednesday) to Holiday.

Also ensures Wednesday weekly-off rows exist on company holiday lists and that
Attendance supports the Holiday status option.
"""

from __future__ import annotations

import frappe
from frappe.utils import getdate

from volunteering.patches.setup_attendance_holiday_status import ensure_holiday_status_option
from volunteering.volunteering.attendance_service import (
	is_org_weekly_off,
	process_employee_attendance,
)
from volunteering.volunteering.leave_setup import WEEKLY_OFF_DAY, ensure_wednesday_weekly_off


def execute():
	ensure_holiday_status_option()
	try:
		ensure_wednesday_weekly_off()
	except Exception:
		frappe.log_error(
			title="Wednesday weekly-off holiday list setup failed",
			message=frappe.get_traceback(),
		)

	rows = frappe.db.sql(
		"""
		select name, employee, attendance_date, status
		from `tabAttendance`
		where docstatus = 1
			and status = 'Absent'
			and weekday(attendance_date) = %s
		order by attendance_date, employee
		""",
		(WEEKLY_OFF_DAY,),
		as_dict=True,
	)

	summary = {"checked": 0, "updated": 0, "skipped": 0, "errors": 0}
	for row in rows:
		summary["checked"] += 1
		attendance_date = getdate(row.attendance_date)
		if not is_org_weekly_off(attendance_date):
			summary["skipped"] += 1
			continue
		try:
			action = process_employee_attendance(row.employee, attendance_date)
			if action in ("updated", "created", "unchanged"):
				# Re-read: success is Holiday (or On Leave if leave exists).
				status = frappe.db.get_value(
					"Attendance",
					{"employee": row.employee, "attendance_date": attendance_date, "docstatus": 1},
					"status",
				)
				if status == "Holiday":
					summary["updated"] += 1
				else:
					summary["skipped"] += 1
			else:
				summary["skipped"] += 1
		except Exception:
			summary["errors"] += 1
			frappe.log_error(
				title=f"Wednesday Absent fix failed for {row.employee} on {attendance_date}",
				message=frappe.get_traceback(),
			)

	frappe.logger("volunteering").info(f"Wednesday Absent → Holiday: {summary}")
	print(f"Wednesday Absent → Holiday: {summary}")
