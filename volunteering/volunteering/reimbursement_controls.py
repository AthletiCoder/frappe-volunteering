# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Purchase Invoice 'paid outside system' + optional reimbursement caps."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)


@frappe.whitelist()
def mark_purchase_invoice_paid_outside(name, remarks=None, posting_date=None):
	"""Mark a submitted Purchase Invoice as paid without a Payment Entry.

	Creates a Journal Entry (Dr Creditors / Cr a clearing or cash account note)
	is intentionally *not* auto-posted here — we stamp an audit custom field and
	set outstanding to paid via a Payment Entry against a configurable mode is
	complex. Instead we:
	  1. Require Accounts role
	  2. Require Outstanding > 0 and docstatus = 1
	  3. Create a Payment Entry (Pay) with mode Manual / Cash and submit it
	     if company bank/cash default exists; else set a custom flag + comment
	     and ask Accounts to complete PE.
	"""
	roles = set(frappe.get_roles())
	if not roles.intersection({"Accounts Manager", "Accounts User", "System Manager"}):
		frappe.throw(_("Only Accounts can mark invoices paid outside the system."), frappe.PermissionError)

	pi = frappe.get_doc("Purchase Invoice", name)
	if pi.docstatus != 1:
		frappe.throw(_("Purchase Invoice must be submitted."))
	if flt(pi.outstanding_amount) <= 0:
		frappe.throw(_("Purchase Invoice has no outstanding amount."))

	remarks = (remarks or "").strip() or _("Paid outside ERPNext")
	posting_date = getdate(posting_date or nowdate())

	# Prefer creating a real Payment Entry so GL stays correct
	try:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		pe = get_payment_entry("Purchase Invoice", pi.name)
		pe.posting_date = posting_date
		pe.remarks = remarks
		cash_account = frappe.db.get_value("Company", pe.company, "default_cash_account")
		if cash_account:
			pe.mode_of_payment = "Cash"
			pe.paid_from = cash_account
		if not pe.reference_no:
			pe.reference_no = f"OUTSIDE-{pi.name}"
		if not pe.reference_date:
			pe.reference_date = posting_date
		if pe.meta.has_field("is_cash_payment"):
			pe.is_cash_payment = 1
		pe.insert(ignore_permissions=True)
		pe.submit()
		frappe.msgprint(
			_("Payment Entry {0} created and submitted for invoice paid outside the system.").format(
				frappe.utils.get_link_to_form("Payment Entry", pe.name)
			),
			indicator="green",
		)
		return pe.name
	except Exception:
		frappe.log_error(title="Mark PI paid outside failed", message=frappe.get_traceback())
		pi.add_comment(
			"Info",
			_("Marked as paid outside system by {0}: {1}. Create Payment Entry manually.").format(
				frappe.session.user, remarks
			),
		)
		frappe.throw(
			_(
				"Could not auto-create Payment Entry (missing bank/cash account?). "
				"A comment was added — please create the Payment Entry manually."
			)
		)


def validate_reimbursement_cap(doc, method=None):
	"""Optional per-employee monthly reimbursement cap on Expense Claim."""
	if doc.doctype != "Expense Claim":
		return
	settings = get_accounting_settings()
	cap = flt(settings.get("monthly_reimbursement_cap") or 0)
	if cap <= 0:
		return

	employee = doc.employee
	if not employee:
		return

	amount_field = "total_claimed_amount"
	this_amount = flt(doc.get(amount_field))
	month_start = getdate(doc.posting_date or nowdate()).replace(day=1)

	existing = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(`{amount_field}`), 0)
		FROM `tabExpense Claim`
		WHERE employee = %s
			AND docstatus < 2
			AND posting_date >= %s
			AND name != %s
			AND IFNULL(workflow_state, '') NOT IN ('Draft', 'Rejected', '')
		""",
		(employee, month_start, doc.name or ""),
	)[0][0]

	total = flt(existing) + this_amount
	if total > cap:
		frappe.throw(
			_(
				"Employee {0} would exceed the monthly reimbursement cap ({1}). "
				"Current month claimed/pending: {2}. This claim: {3}."
			).format(
				employee,
				frappe.format_value(cap, "Currency"),
				frappe.format_value(existing, "Currency"),
				frappe.format_value(this_amount, "Currency"),
			),
			title=_("Reimbursement Cap Exceeded"),
		)
