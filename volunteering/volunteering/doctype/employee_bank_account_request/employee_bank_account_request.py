import frappe
from frappe import _
from frappe.model.document import Document


class EmployeeBankAccountRequest(Document):
	def validate(self):
		from volunteering.volunteering.employee_bank_accounts import request_mutation_allowed

		if not request_mutation_allowed():
			frappe.throw(
				_("Use the employee bank-account approval workflow; requests cannot be edited directly."),
				frappe.PermissionError,
			)

	def on_trash(self):
		frappe.throw(
			_("Bank-account requests are retained as audit history and cannot be deleted."),
			frappe.PermissionError,
		)
