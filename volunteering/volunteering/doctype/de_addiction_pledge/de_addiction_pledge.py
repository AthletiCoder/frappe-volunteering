# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import secrets
import string

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from volunteering.volunteering.doctype.volunteer.volunteer import format_mobile_number

# 8-char shareable ID: A–Z / 0–9, never starts with 0
PLEDGE_UUID_LENGTH = 8
PLEDGE_UUID_ALPHABET = string.ascii_uppercase + string.digits
PLEDGE_UUID_FIRST = string.ascii_uppercase + "123456789"


def generate_pledge_uuid(length: int = PLEDGE_UUID_LENGTH) -> str:
	"""Return a unique uppercase alphanumeric pledge ID (does not start with 0)."""
	if length < 2:
		frappe.throw("Pledge UUID length must be at least 2")

	for _ in range(50):
		code = secrets.choice(PLEDGE_UUID_FIRST) + "".join(
			secrets.choice(PLEDGE_UUID_ALPHABET) for _ in range(length - 1)
		)
		if not frappe.db.exists("De Addiction Pledge", {"pledge_uuid": code}):
			return code

	frappe.throw("Could not generate a unique pledge ID. Please try again.")


class DeAddictionPledge(Document):
	def before_validate(self):
		if not self.pledge_uuid:
			self.pledge_uuid = generate_pledge_uuid()
		self.status = self.status or "Draft"
		self.source = self.source or "Interakt"
		if not self.started_on:
			self.started_on = now_datetime()

	def validate(self):
		if self.mobile_number:
			formatted = format_mobile_number(self.mobile_number)
			if formatted:
				self.mobile_number = formatted

		if self.people_count is not None and self.people_count < 0:
			frappe.throw("People count cannot be negative")
