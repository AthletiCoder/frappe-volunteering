# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from volunteering.volunteering.manager_note_permissions import can_create_manager_note


class ManagerNote(Document):
	def before_insert(self):
		self.authored_by = frappe.session.user
		self.authored_on = now_datetime()
		if not can_create_manager_note(self):
			frappe.throw(_("Only managers or HR can add Manager Notes."), frappe.PermissionError)

	def validate(self):
		if self.is_new():
			return
		# Append-only: block content changes after insert (System Manager may force).
		if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
			return
		previous = self.get_doc_before_save()
		if not previous:
			return
		for field in ("employee", "note_date", "note_type", "content", "authored_by", "authored_on"):
			if self.get(field) != previous.get(field):
				frappe.throw(_("Manager Notes are append-only and cannot be edited."))

	def on_trash(self):
		if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
			return
		frappe.throw(_("Manager Notes cannot be deleted."), frappe.PermissionError)
