# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def on_payment_entry_submit(doc, method=None):
	"""Notify party / owner that payment completed."""
	recipients = []
	if doc.party_type == "Employee" and doc.party:
		user = frappe.db.get_value("Employee", doc.party, "user_id")
		if user:
			email = frappe.db.get_value("User", user, "email")
			if email:
				recipients.append(email)
	if doc.owner:
		email = frappe.db.get_value("User", doc.owner, "email")
		if email and email not in recipients:
			recipients.append(email)

	if not recipients:
		return

	frappe.sendmail(
		recipients=recipients,
		subject=_("Payment completed: {0}").format(doc.name),
		message=_(
			"Payment Entry {0} for {1} {2} has been submitted. Amount: {3}."
		).format(
			doc.name,
			doc.party_type or "",
			doc.party or "",
			frappe.format_value(doc.paid_amount or doc.received_amount or 0, "Currency"),
		),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		now=True,
	)
