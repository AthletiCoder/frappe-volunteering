# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Spend path guards: vendor preference, cash limit, emergency, invoice-split warnings."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate

from volunteering.volunteering.approval_routing import get_document_amount
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)

SPEND_GUIDE_URL = "/help/accounts/how-to-spend"


def validate_spend_controls(doc, method=None):
	if doc.doctype == "Expense Claim":
		_warn_prefer_vendor_payment(doc)
		_warn_invoice_split(doc)
		_validate_emergency(doc)
	elif doc.doctype == "Purchase Order":
		_validate_emergency(doc)
		_warn_invoice_split(doc)
	elif doc.doctype == "Payment Entry":
		_validate_cash_payment(doc)


def _warn_prefer_vendor_payment(doc):
	settings = get_accounting_settings()
	threshold = flt(settings.get("vendor_payment_threshold") or 5000)
	amount = get_document_amount(doc)
	if amount <= threshold:
		return

	if doc.get("is_emergency"):
		return

	reason = (doc.get("vendor_override_reason") or "").strip()
	message = _(
		"Amount {0} is above the vendor payment threshold ({1}). "
		"Prefer a <a href='/app/purchase-order/new'>Purchase Order</a> / vendor payment. "
		"To continue as reimbursement, enter a Vendor Payment Override Reason. "
		'<a href="{2}" target="_blank">How to spend</a>'
	).format(
		frappe.format_value(amount, "Currency"),
		frappe.format_value(threshold, "Currency"),
		SPEND_GUIDE_URL,
	)

	if doc.workflow_state not in (None, "", "Draft", "Rejected") and not reason:
		frappe.throw(message, title=_("Prefer Vendor Payment"))

	frappe.msgprint(message, indicator="orange", title=_("Prefer Vendor Payment"))


def _warn_invoice_split(doc):
	settings = get_accounting_settings()
	window = int(settings.get("invoice_split_window_days") or 7)
	if window <= 0:
		return

	project = doc.get("project")
	if not project:
		return

	employee = doc.get("employee")
	if not employee and doc.doctype == "Purchase Order":
		employee = frappe.db.get_value("Employee", {"user_id": doc.owner}, "name")

	if not employee:
		return

	supplier = doc.get("supplier") if doc.doctype == "Purchase Order" else None
	posting = getdate(doc.get("posting_date") or doc.get("transaction_date") or frappe.utils.today())
	from_date = add_days(posting, -window)

	related = []
	amount_total = get_document_amount(doc)

	# Same doctype peers
	filters = {
		"project": project,
		"docstatus": ["!=", 2],
		"name": ["!=", doc.name or ""],
	}
	date_field = "posting_date" if doc.doctype == "Expense Claim" else "transaction_date"
	if frappe.db.has_column(doc.doctype, date_field):
		filters[date_field] = [">=", from_date]
	if doc.doctype == "Expense Claim":
		filters["employee"] = employee
	if supplier and frappe.db.has_column(doc.doctype, "supplier"):
		filters["supplier"] = supplier
	if frappe.db.has_column(doc.doctype, "workflow_state"):
		filters["workflow_state"] = ["not in", ["Draft", "Rejected", ""]]

	amount_field = "total_claimed_amount" if doc.doctype == "Expense Claim" else "grand_total"
	for row in frappe.get_all(doc.doctype, filters=filters, fields=["name", amount_field]):
		related.append(row.name)
		amount_total += flt(row.get(amount_field))

	if not related:
		return

	frappe.msgprint(
		_(
			"Possible split procurement: {0} similar {1}(s) for the same project/employee"
			"{2} within {3} days. Combined amount ≈ {4}. Review before approving."
		).format(
			len(related),
			doc.doctype,
			_(" / vendor") if supplier else "",
			window,
			frappe.format_value(amount_total, "Currency"),
		),
		indicator="orange",
		title=_("Invoice Split Warning"),
	)


def _validate_emergency(doc):
	if not doc.get("is_emergency"):
		return

	settings = get_accounting_settings()
	submit_days = int(settings.get("emergency_submit_working_days") or 1)
	# Soft guidance on save; hard check when leaving Draft
	if doc.workflow_state in (None, "", "Draft"):
		frappe.msgprint(
			_(
				"Emergency purchase: submit within {0} working day(s) and ensure approval "
				"within {1} working day(s)."
			).format(
				submit_days,
				int(settings.get("emergency_approve_working_days") or 2),
			),
			indicator="blue",
			title=_("Emergency"),
		)


def _validate_cash_payment(doc):
	settings = get_accounting_settings()
	limit = flt(settings.get("cash_payment_limit") or 2000)
	mode = (doc.get("mode_of_payment") or "").strip()
	is_cash = mode.lower() == "cash"
	if frappe.db.has_column("Payment Entry", "is_cash_payment"):
		doc.is_cash_payment = 1 if is_cash else 0

	if not is_cash:
		return

	amount = flt(doc.get("paid_amount") or doc.get("received_amount") or 0)
	if amount > limit:
		frappe.throw(
			_(
				"Cash payments cannot exceed {0}. Use a digital Mode of Payment "
				"(NEFT/UPI/bank transfer)."
			).format(frappe.format_value(limit, "Currency")),
			title=_("Cash Limit Exceeded"),
		)
