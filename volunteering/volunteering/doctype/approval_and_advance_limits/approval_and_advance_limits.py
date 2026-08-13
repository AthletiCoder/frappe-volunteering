# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ApprovalandAdvanceLimits(Document):
	def validate(self):
		seen = set()
		for row in self.designation_limits or []:
			if row.designation in seen:
				frappe.throw(
					_("Row {0}: Grade {1} is listed more than once.").format(
						row.idx, frappe.bold(row.designation)
					)
				)
			seen.add(row.designation)

			if flt(row.max_approve_amount) < 0 or flt(row.max_advance_amount) < 0:
				frappe.throw(_("Row {0}: Limits cannot be negative.").format(row.idx))

	def on_update(self):
		frappe.clear_cache(doctype="Approval and Advance Limits")


@frappe.whitelist()
def reset_to_defaults():
	"""Replace the limits table with the built-in grade defaults."""
	frappe.only_for(("System Manager", "Accounts Manager"))

	from volunteering.volunteering.accounting_setup import ensure_employee_grades
	from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
		DEFAULT_GRADE_LIMITS,
	)

	ensure_employee_grades()

	doc = frappe.get_doc("Approval and Advance Limits")
	doc.set("designation_limits", [])
	for grade, max_approve, max_advance in DEFAULT_GRADE_LIMITS:
		if not frappe.db.exists("Employee Grade", grade):
			continue
		doc.append(
			"designation_limits",
			{
				"designation": grade,
				"max_approve_amount": max_approve,
				"max_advance_amount": max_advance,
			},
		)
	doc.save(ignore_permissions=True)
	return len(doc.designation_limits)
