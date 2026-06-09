import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, nowdate

from volunteering.volunteering.daily_work_log_permissions import can_review_work_log


class DailyWorkLog(Document):
	def autoname(self):
		self.name = f"{self.employee}-{getdate(self.date)}"

	def validate(self):
		self.set_total_hours()
		self.validate_items()
		self.validate_duplicate_log()
		self.validate_backdate()
		self.validate_wfh()
		self.validate_review_status()
		self.show_hours_warning()

	def before_save(self):
		self.set_total_hours()

	def on_submit(self):
		self.db_set("status", "Submitted", update_modified=False)

	def set_total_hours(self):
		self.total_hours = sum(flt(item.time_spent_hours) for item in self.items)

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one work log item is required."))

		if flt(self.total_hours) <= 0:
			frappe.throw(_("Total hours must be greater than zero."))

		for idx, item in enumerate(self.items, start=1):
			if flt(item.time_spent_hours) <= 0:
				frappe.throw(_("Row {0}: Time spent must be greater than zero.").format(idx))

			description = (item.description or "").strip()
			if len(description) <= 10:
				frappe.throw(_("Row {0}: Description must be more than 10 characters.").format(idx))

	def validate_duplicate_log(self):
		if frappe.db.exists(
			"Daily Work Log",
			{
				"employee": self.employee,
				"date": self.date,
				"name": ["!=", self.name],
				"docstatus": ["<", 2],
			},
		):
			frappe.throw(_("A Daily Work Log already exists for this employee on {0}.").format(self.date))

	def validate_backdate(self):
		settings = get_daily_work_log_settings()
		limit_days = cint(settings.get("backdate_limit_days") or 2)
		earliest_allowed = add_days(getdate(nowdate()), -limit_days)

		if getdate(self.date) < earliest_allowed:
			frappe.throw(
				_("Daily Work Logs cannot be backdated beyond {0} days. Earliest allowed date is {1}.").format(
					limit_days,
					earliest_allowed,
				)
			)

	def validate_wfh(self):
		if not self.employee or not self.date:
			return

		from volunteering.volunteering.attendance_service import has_approved_wfh_request_for_employee

		has_wfh_request = has_approved_wfh_request_for_employee(self.employee, self.date)
		if self.is_wfh and not has_wfh_request:
			frappe.throw(
				_("Work From Home requires an approved Attendance Request for this date.")
			)

		if has_wfh_request:
			self.is_wfh = 1

	def validate_review_status(self):
		if self.status != "Reviewed" or self.is_new():
			return

		previous_status = self.get_doc_before_save().status if self.get_doc_before_save() else None
		if previous_status == "Reviewed":
			return

		if not can_review_work_log(self):
			frappe.throw(_("Only a manager or HR user can mark this log as Reviewed."))

		if self.docstatus != 1:
			frappe.throw(_("Only submitted logs can be marked as Reviewed."))

	def show_hours_warning(self):
		settings = get_daily_work_log_settings()
		min_hours = flt(settings.get("min_hours_warning") or 4)

		if flt(self.total_hours) < min_hours:
			frappe.msgprint(
				_("Total hours ({0}) is below the recommended minimum of {1} hours.").format(
					self.total_hours,
					min_hours,
				),
				indicator="orange",
				title=_("Low Hours"),
			)

	@frappe.whitelist()
	def mark_as_reviewed(self):
		if self.docstatus != 1:
			frappe.throw(_("Only submitted logs can be marked as Reviewed."))

		if not can_review_work_log(self):
			frappe.throw(_("Only a manager or HR user can mark this log as Reviewed."), frappe.PermissionError)

		self.status = "Reviewed"
		self.save(ignore_permissions=True)
		return self.name


def get_daily_work_log_settings():
	if frappe.db.exists("DocType", "Daily Work Log Settings"):
		return frappe.get_single("Daily Work Log Settings").as_dict()

	return {
		"backdate_limit_days": 2,
		"min_hours_warning": 4,
		"enable_attendance_job": 1,
	}
