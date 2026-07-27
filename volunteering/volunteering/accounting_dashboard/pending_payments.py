import frappe
from frappe import _
from frappe.utils import flt, formatdate, nowdate

from volunteering.volunteering.accounting_dashboard.constants import ACCOUNTS_ROLES


def _require_accounts_access():
	user = frappe.session.user
	if user == "Administrator":
		return
	if not ACCOUNTS_ROLES.intersection(frappe.get_roles(user)):
		frappe.throw(_("Accounts access required."), frappe.PermissionError)


@frappe.whitelist()
def get_pending_reimbursements():
	"""Approved, submitted expense claims awaiting employee reimbursement."""
	_require_accounts_access()

	claims = frappe.get_all(
		"Expense Claim",
		filters={
			"docstatus": 1,
			"approval_status": "Approved",
			"status": "Unpaid",
		},
		fields=[
			"name",
			"employee",
			"employee_name",
			"project",
			"company",
			"total_claimed_amount",
			"grand_total",
			"posting_date",
			"modified",
		],
		order_by="posting_date asc",
	)

	for row in claims:
		row.amount = flt(row.grand_total or row.total_claimed_amount)
		row.modified_label = formatdate(row.modified)
		row.route = f"/app/expense-claim/{row.name}"

	return claims


@frappe.whitelist()
def get_pending_vendor_payments():
	"""Approved, submitted purchase invoices with outstanding balance."""
	_require_accounts_access()

	invoices = frappe.get_all(
		"Purchase Invoice",
		filters={
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
		fields=[
			"name",
			"supplier",
			"supplier_name",
			"project",
			"company",
			"grand_total",
			"outstanding_amount",
			"posting_date",
			"due_date",
			"modified",
		],
		order_by="due_date asc, posting_date asc",
	)

	for row in invoices:
		row.amount = flt(row.outstanding_amount or row.grand_total)
		row.modified_label = formatdate(row.modified)
		row.due_date_label = formatdate(row.due_date) if row.due_date else ""
		row.route = f"/app/purchase-invoice/{row.name}"

	return invoices
