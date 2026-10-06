import frappe
from frappe.model.document import Document

from volunteering.volunteering.invoice_generator import _signature_png


class DonationReceiptSignatory(Document):
	def validate(self):
		if not (self.signatory_name or "").strip():
			frappe.throw("Authorised signatory name is required.")
		if not _signature_png(self.signature_data):
			frappe.throw("Draw the authorised signatory's signature before saving.")
