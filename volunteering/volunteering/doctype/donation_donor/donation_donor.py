import re

import frappe
from frappe.model.document import Document

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class DonationDonor(Document):
	def validate(self):
		self.donor_name = (self.donor_name or "").strip()
		self.pan = (self.pan or "").strip().upper()
		self.email = (self.email or "").strip().lower()
		if not self.donor_name:
			frappe.throw("Donor name is required.")
		if self.pan and not PAN_RE.fullmatch(self.pan):
			frappe.throw("Enter a valid donor PAN or leave it blank.")
