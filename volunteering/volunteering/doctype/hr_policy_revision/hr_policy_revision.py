from frappe.model.document import Document
import frappe


class HRPolicyRevision(Document):
	def validate(self):
		if not self.is_new() or not self.flags.policy_publication:
			frappe.throw("Published HR policies are immutable. Publish a new dated revision.")
	def on_trash(self):
		frappe.throw("Published HR policies must be retained as history.")
