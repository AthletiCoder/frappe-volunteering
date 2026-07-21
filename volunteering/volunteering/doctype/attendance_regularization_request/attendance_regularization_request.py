# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from volunteering.volunteering.attendance_service import ensure_attendance, get_submitted_work_log_hours


class AttendanceRegularizationRequest(Document):
	def validate(self):
		self.validate_duplicate()
		if not self.employee_name and self.employee:
			self.employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")

	def validate_duplicate(self):
		filters = {
			"employee": self.employee,
			"attendance_date": self.attendance_date,
			"docstatus": ["<", 2],
			"status": ["in", ["Open", "Approved"]],
		}
		if not self.is_new():
			filters["name"] = ["!=", self.name]

		if frappe.db.exists("Attendance Regularization Request", filters):
			frappe.throw(
				_("An open or approved regularization already exists for {0} on {1}.").format(
					self.employee, self.attendance_date
				)
			)

	def before_submit(self):
		if self.status == "Open":
			self.status = "Approved"

	def on_submit(self):
		if self.status != "Approved":
			return
		self.apply_attendance()

	def on_cancel(self):
		self.status = "Rejected"
		self.db_set("status", "Rejected")

	def apply_attendance(self):
		hours = get_submitted_work_log_hours(self.employee, self.attendance_date)
		leave_type = None
		if self.requested_status == "On Leave":
			leave_type = (
				frappe.db.get_single_value("Leave Policy Settings", "default_leave_type")
				or "Privilege Leave"
			)

		ensure_attendance(
			employee=self.employee,
			attendance_date=getdate(self.attendance_date),
			status=self.requested_status,
			leave_type=leave_type,
			working_hours=hours,
			half_day_status="Present" if self.requested_status == "Half Day" else None,
		)
		attendance_name = frappe.db.get_value(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"docstatus": 1,
			},
			"name",
		)
		if attendance_name and frappe.db.has_column("Attendance", "custom_regularized"):
			frappe.db.set_value("Attendance", attendance_name, "custom_regularized", 1)

		frappe.get_doc("Attendance Regularization Request", self.name).add_comment(
			"Info",
			_("Attendance updated to {0} via regularization.").format(self.requested_status),
		)

	@frappe.whitelist()
	def reject_request(self):
		if self.docstatus != 0:
			frappe.throw(_("Only open requests can be rejected."))
		if not _can_approve(self):
			frappe.throw(_("Not permitted to reject this request."), frappe.PermissionError)
		self.status = "Rejected"
		self.save(ignore_permissions=True)
		return self.name

	@frappe.whitelist()
	def approve_request(self):
		if self.docstatus != 0:
			frappe.throw(_("Only open requests can be approved."))
		if not _can_approve(self):
			frappe.throw(_("Not permitted to approve this request."), frappe.PermissionError)
		self.status = "Approved"
		self.save(ignore_permissions=True)
		self.submit()
		return self.name


def _can_approve(doc):
	user = frappe.session.user
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	if roles.intersection({"HR Manager", "HR User", "System Manager"}):
		return True
	manager = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not manager:
		return False
	return frappe.db.get_value("Employee", doc.employee, "reports_to") == manager
