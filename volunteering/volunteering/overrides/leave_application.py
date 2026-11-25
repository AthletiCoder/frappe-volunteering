"""Keep HRMS leave ledgers while using the employee's dated working calendar."""
import frappe
from frappe import _
from frappe.utils import getdate, add_days
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication
from hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry import create_leave_ledger_entry


class SevamritaLeaveApplication(LeaveApplication):
	def validate(self):
		from volunteering.volunteering.hr_policy import hr_leave_validation_access
		with hr_leave_validation_access():
			return super().validate()

	def validate_attendance(self):
		from volunteering.volunteering.hr_policy import override_reason
		from volunteering.volunteering.hr_leave_balances import require_unprocessed_salary
		if override_reason(self):
			require_unprocessed_salary(self.employee, self.from_date, self.to_date)
			return
		return super().validate_attendance()

	def update_attendance(self):
		if not self.get("sf_policy_revision"): return super().update_attendance()
		if self.status != "Approved": return
		from volunteering.volunteering.attendance_service import process_employee_attendance
		start, end = getdate(self.from_date), getdate(self.to_date)
		while start <= end:
			process_employee_attendance(self.employee, start, force_regularized=True)
			start = getdate(add_days(start, 1))

	def create_leave_ledger_entry(self, submit=True):
		if not self.get("sf_policy_revision"): return super().create_leave_ledger_entry(submit)
		if self.status != "Approved" and submit: return
		from volunteering.volunteering.time_leave_portal import leave_units
		from volunteering.volunteering.employee_calendars import sync_employee_calendar
		if not submit:
			create_leave_ledger_entry(self, {}, submit=False)
			return
		for day, units in leave_units(self.employee, self.from_date, self.to_date, self.half_day, self.half_day_date, include_holidays=self.leave_type == "Maternity Leave"):
			create_leave_ledger_entry(self, {"leaves": -units, "from_date": day, "to_date": day,
				"is_lwp": int(bool(frappe.db.get_value("Leave Type", self.leave_type, "is_lwp"))),
				"holiday_list": sync_employee_calendar(self.employee, day.year) or ""})


def prepare_leave_policy(doc, method=None):
	from volunteering.volunteering.hr_policy import policy_on
	from volunteering.volunteering.employee_calendars import sync_employee_calendar
	if not doc.employee or not doc.from_date or not doc.to_date: return
	if not doc.is_new() and doc.has_value_changed("sf_policy_revision"):
		frappe.throw(_("The HR policy reference is assigned by the server."), frappe.PermissionError)
	if doc.is_new() or (doc.docstatus == 0 and any(doc.has_value_changed(key) for key in ("employee", "from_date", "to_date"))):
		doc.sf_policy_revision = policy_on(doc.from_date).get("_revision")
	from volunteering.volunteering.hr_special_leave import SPECIAL, prepare_special
	if doc.leave_type in SPECIAL:
		doc.leave_category = "Normal"
		prepare_special(doc.employee,doc.leave_type,getdate(doc.from_date),getdate(doc.to_date),{"name":doc.name,"childbirth_date":doc.get("sf_childbirth_date"),"parental_case":doc.get("sf_parental_case"),"half_day":doc.half_day})
	if not doc.is_new() and doc.get("sf_eligibility_verified_by") and any(doc.has_value_changed(key) for key in ("employee","leave_type","from_date","to_date","sf_childbirth_date","sf_parental_case")):
		doc.sf_eligibility_verified_by=None;doc.sf_eligibility_reason=None;doc.flags.eligibility_service=True
	if doc.get("sf_policy_revision"):
		for year in range(getdate(doc.from_date).year, getdate(doc.to_date).year+1): sync_employee_calendar(doc.employee, year)
