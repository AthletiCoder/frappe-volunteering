import frappe
from frappe.model.document import Document
from frappe.utils import add_days, nowdate


class DailyWorkLogSettings(Document):
	pass


@frappe.whitelist()
def trigger_attendance_job(attendance_date=None):
	frappe.only_for(("HR Manager", "System Manager"))

	from volunteering.volunteering.attendance_service import process_daily_attendance

	if not attendance_date:
		attendance_date = add_days(nowdate(), -1)

	return process_daily_attendance(attendance_date=attendance_date, manual=True)
