import frappe
from frappe.model.document import Document


class HRLeavePosting(Document):
	def validate(self):
		if not self.is_new() or not self.flags.policy_posting:
			frappe.throw("Leave postings are immutable. Create a reasoned adjustment instead.")
	def on_trash(self):
		frappe.throw("Leave postings must be retained as history.")
