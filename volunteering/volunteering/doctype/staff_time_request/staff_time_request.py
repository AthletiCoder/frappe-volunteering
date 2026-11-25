from frappe.model.document import Document
import frappe


class StaffTimeRequest(Document):
	def validate(self):
		if not self.flags.time_service:
			frappe.throw("Use Time and leave to create or decide this request.", frappe.PermissionError)
	def on_trash(self):
		frappe.throw("Time requests are retained as history. Cancel an open request instead.")
