import re

import frappe
from frappe.model.document import Document

from volunteering.volunteering.doctype.volunteer.volunteer import format_mobile_number

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class Donation(Document):
	def validate(self):
		self.currency = self.currency or "INR"
		self.source = self.source or "Gateway"
		self.status = self.status or "Initiated"

		if self.mobile_number:
			formatted = format_mobile_number(self.mobile_number)
			if formatted:
				self.mobile_number = formatted

		if self.amount is None or float(self.amount) <= 0:
			frappe.throw("Donation amount must be greater than zero")

		if self.want_80g:
			pan = (self.pan or "").strip().upper()
			self.pan = pan
			if not PAN_RE.match(pan):
				frappe.throw("Enter a valid PAN (e.g. ABCDE1234F) to claim 80G")
			if not (self.address or "").strip():
				frappe.throw("Address is required when 80G is requested")
		elif self.pan:
			self.pan = (self.pan or "").strip().upper()
