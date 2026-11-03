from frappe.model.document import Document
import frappe


class CollaborationDocument(Document):
	def validate(self):
		if not self.flags.collaboration_write:
			frappe.throw("Use the Chat & workspaces interface to change collaboration records.", frappe.PermissionError)

	def on_trash(self):
		if not self.flags.collaboration_write:
			frappe.throw("Use the Chat & workspaces interface to remove collaboration records.", frappe.PermissionError)
