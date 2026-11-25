from frappe.model.document import Document
import frappe


class HRHoliday(Document):
	def validate(self):
		if not self.flags.hr_resource_service:
			frappe.throw("Use the People centre to update this record.", frappe.PermissionError)
	def on_trash(self):
		frappe.throw("Keep this record for audit history.")
