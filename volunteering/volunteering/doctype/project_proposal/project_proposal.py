from frappe.model.document import Document


class ProjectProposal(Document):
	def validate(self):
		from volunteering.volunteering.project_proposals import validate_request_mutation
		validate_request_mutation(self)

	def on_trash(self):
		import frappe
		frappe.throw("Project requests are retained for audit history; withdraw drafts instead of deleting them.")
